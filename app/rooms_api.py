"""Rooms over HTTP: create, list, read, configure, rename and delete.

Only the owner changes settings, delegates, the short name, or deletes the room.
Changes reach a live room through its command queue.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app.auth.access import OWNER
from app.auth.identity import Identity
from app.auth.oauth import Auth
from app.room.errors import CommandError
from app.room.live import RoomRegistry
from app.room.room import MAX_TIMER
from app.room.scales import Scale, number
from app.store.rooms import Delegate, RoomRecord, RoomStore, SlugTaken
from app.web import check_write

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
MAX_DELEGATES = 100
SETTINGS_FIELDS = {"slug", "scale", "timer_seconds", "sound", "delegates"}

router = APIRouter()


# Shared request checks


async def json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(422, "The body is not valid JSON.") from None
    if not isinstance(body, dict):
        raise HTTPException(422, "The body must be a JSON object.")
    return body


def _auth(request: Request) -> Auth:
    return request.app.state.auth


def _store(request: Request) -> RoomStore:
    return request.app.state.store


def _rooms(request: Request) -> RoomRegistry:
    return request.app.state.rooms


def signed_in(request: Request) -> Identity:
    identity = _auth(request).identity(request.cookies)
    if identity is None:
        raise HTTPException(401, "Sign in first.")
    return identity


async def _record(request: Request, slug: str) -> RoomRecord:
    store = _store(request)
    current = await asyncio.to_thread(store.resolve, slug)
    record = await asyncio.to_thread(store.get, current) if current else None
    if record is None:
        raise HTTPException(404, "No such room.")
    return record


# Routes


@router.get("/api/rooms")
async def list_rooms(request: Request) -> list[dict[str, Any]]:
    identity = signed_in(request)
    found = await asyncio.to_thread(_store(request).rooms_for, identity)
    return [{"slug": record.slug, "access": access} for record, access in found]


@router.post("/api/rooms", status_code=201)
async def create_room(request: Request) -> dict[str, Any]:
    check_write(request)
    identity = signed_in(request)
    if not _auth(request).can_create(identity):
        raise HTTPException(403, "This account may not create rooms.")
    slug = _slug((await json_body(request)).get("slug"))
    record = RoomRecord(slug=slug, owner=identity.key, owner_label=identity.label)
    try:
        record = await asyncio.to_thread(_store(request).create, record)
    except SlugTaken:
        raise HTTPException(409, f"The name {slug} is taken.") from None
    return view(request, record, OWNER)


@router.get("/api/rooms/{slug}")
async def read_room(slug: str, request: Request) -> dict[str, Any]:
    record = await _record(request, slug)
    identity = _auth(request).identity(request.cookies)
    return view(request, record, record.access(identity))


@router.patch("/api/rooms/{slug}")
async def update_room(slug: str, request: Request) -> dict[str, Any]:
    check_write(request)
    identity = signed_in(request)
    record = await _record(request, slug)
    if record.access(identity) != OWNER:
        raise HTTPException(403, "Only the room's owner can change its settings.")
    body = await json_body(request)
    unknown = set(body) - SETTINGS_FIELDS
    if unknown:
        raise HTTPException(422, f"Unknown settings: {', '.join(sorted(unknown))}.")

    changes: dict[str, Any] = {}
    try:
        if "scale" in body:
            changes["scale"] = Scale.from_dict(body["scale"])
    except CommandError as err:
        raise HTTPException(422, err.message) from None
    if "timer_seconds" in body:
        changes["timer_seconds"] = _timer(body["timer_seconds"])
    if "sound" in body:
        if not isinstance(body["sound"], bool):
            raise HTTPException(422, "Sound is true or false.")
        changes["sound"] = body["sound"]
    if "delegates" in body:
        changes["delegates"] = _delegates(body["delegates"])
    new_slug = _slug(body["slug"]) if "slug" in body else record.slug

    store = _store(request)
    old_slug = record.slug
    if new_slug != old_slug:
        try:
            record = await asyncio.to_thread(store.rename, old_slug, new_slug)
        except SlugTaken:
            raise HTTPException(409, f"The name {new_slug} is taken.") from None
    if changes:
        record = await asyncio.to_thread(lambda: store.update(record.slug, **changes))
    await _rooms(request).update(record, moved_from=old_slug if new_slug != old_slug else None)
    return view(request, record, OWNER)


@router.delete("/api/rooms/{slug}", status_code=204)
async def delete_room(slug: str, request: Request) -> Response:
    check_write(request)
    identity = signed_in(request)
    record = await _record(request, slug)
    if record.access(identity) != OWNER:
        raise HTTPException(403, "Only the room's owner can delete it.")
    await asyncio.to_thread(_store(request).delete, record.slug)
    await _rooms(request).delete(record.slug)
    return Response(status_code=204)


# Validation and views


def view(request: Request, record: RoomRecord, access: str | None) -> dict[str, Any]:
    """The room as its viewer may see it. Only the owner sees the settings."""
    result: dict[str, Any] = {"slug": record.slug, "access": access}
    if access == OWNER:
        jira = record.jira
        result["settings"] = {
            "scale": record.scale.to_dict(),
            "timer_seconds": number(record.timer_seconds),
            "sound": record.sound,
            "delegates": [d.to_dict() for d in record.delegates],
            "jira": {
                "available": request.app.state.settings.atlassian is not None,
                "connected": jira.connected,
                "email": jira.email,
                "site": {"cloud_id": jira.cloud_id, "name": jira.site_name, "url": jira.site_url}
                if jira.has_board
                else None,
                "board": {"id": jira.board_id, "name": jira.board_name} if jira.has_board else None,
            },
        }
    return result


def _slug(value: Any) -> str:
    if not isinstance(value, str) or not SLUG.match(value):
        raise HTTPException(
            422,
            "A short name is 1 to 40 lowercase letters, digits or hyphens,"
            " starting with a letter or digit.",
        )
    return value


def _timer(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not 1 <= value <= MAX_TIMER:
        raise HTTPException(422, f"The default countdown is 1 to {MAX_TIMER} seconds.")
    return float(value)


def _delegates(value: Any) -> list[Delegate]:
    if not isinstance(value, list) or len(value) > MAX_DELEGATES:
        raise HTTPException(422, f"Delegates are a list of at most {MAX_DELEGATES}.")
    found = []
    for entry in value:
        if not isinstance(entry, dict):
            raise HTTPException(422, "Each delegate is {provider, identifier}.")
        provider, identifier = entry.get("provider"), entry.get("identifier")
        if not isinstance(identifier, str):
            raise HTTPException(422, "Each delegate needs an email or GitHub username.")
        identifier = identifier.strip()
        if provider == "google" and EMAIL.match(identifier):
            found.append(Delegate("google", identifier.lower()))
        elif provider == "github" and GITHUB_LOGIN.match(identifier):
            found.append(Delegate("github", identifier.lower()))
        else:
            raise HTTPException(422, f"{identifier!r} is not a valid {provider} delegate.")
    return found
