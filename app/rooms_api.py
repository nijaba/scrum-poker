"""Rooms over HTTP: create, list, read, configure, rename, delete and hand over.

The owner and co-owners change settings, delegates and the short name. Only the owner
deletes the room or offers it to a delegate, and only the offered account accepts.
Changes reach a live room through its command queue.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app.auth.access import MANAGERS, OWNER, ROLES
from app.auth.identity import Identity
from app.auth.oauth import Auth
from app.demo.rooms import PREFIX as DEMO_PREFIX
from app.room.errors import CommandError
from app.room.live import RoomRegistry
from app.room.queue_filter import FilterError, QueueFilter
from app.room.room import MAX_TIMER
from app.room.scales import Scale, number
from app.store.rooms import (
    Delegate,
    NoOffer,
    NotOffered,
    RoomRecord,
    RoomStore,
    SlugTaken,
)
from app.web import check_write

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
MAX_DELEGATES = 100
SETTINGS_FIELDS = {"slug", "scale", "timer_seconds", "sound", "auto_reveal", "delegates"}
SETTINGS_FIELDS |= {"queue_filter"}

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
    return [
        {"slug": record.slug, "access": access, "offer": offer_for(record, identity)}
        for record, access in found
    ]


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
    demo = request.app.state.demo
    if demo is not None and demo.get(slug) is not None:
        return {"slug": slug, "access": None, "demo": True}
    record = await _record(request, slug)
    identity = _auth(request).identity(request.cookies)
    result = view(request, record, record.access(identity))
    if record.offered_to(identity):
        result["offer"] = offer_for(record, identity)
    return result


@router.patch("/api/rooms/{slug}")
async def update_room(slug: str, request: Request) -> dict[str, Any]:
    check_write(request)
    identity = signed_in(request)
    record = await _record(request, slug)
    access = record.access(identity)
    if access not in MANAGERS:
        raise HTTPException(403, "Only the room's owner or a co-owner can change its settings.")
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
    if "auto_reveal" in body:
        if not isinstance(body["auto_reveal"], bool):
            raise HTTPException(422, "Auto-reveal is true or false.")
        changes["auto_reveal"] = body["auto_reveal"]
    if "delegates" in body:
        changes["delegates"] = _delegates(body["delegates"])
    if "queue_filter" in body:
        changes["queue_filter"] = queue_filter(body["queue_filter"])
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
    return view(request, record, access)


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


@router.post("/api/rooms/{slug}/ownership")
async def offer_ownership(slug: str, request: Request) -> dict[str, Any]:
    check_write(request)
    identity = signed_in(request)
    record = await _record(request, slug)
    if record.access(identity) != OWNER:
        raise HTTPException(403, "Only the room's owner can hand it over.")
    body = await json_body(request)
    delegate = Delegate(str(body.get("provider")), str(body.get("identifier", "")).lower())
    if delegate.provider not in ("google", "github") or not any(
        (d.provider, d.identifier) == (delegate.provider, delegate.identifier)
        for d in record.delegates
    ):
        raise HTTPException(422, "The room can only be offered to one of its delegates.")
    record = await asyncio.to_thread(_store(request).offer_ownership, record.slug, delegate)
    await _rooms(request).update(record)
    return view(request, record, OWNER)


@router.delete("/api/rooms/{slug}/ownership", status_code=204)
async def cancel_ownership_offer(slug: str, request: Request) -> Response:
    check_write(request)
    identity = signed_in(request)
    record = await _record(request, slug)
    if record.access(identity) != OWNER:
        raise HTTPException(403, "Only the room's owner can cancel the offer.")
    record = await asyncio.to_thread(_store(request).cancel_offer, record.slug)
    await _rooms(request).update(record)
    return Response(status_code=204)


@router.post("/api/rooms/{slug}/ownership/accept")
async def accept_ownership(slug: str, request: Request) -> dict[str, Any]:
    check_write(request)
    identity = signed_in(request)
    record = await _record(request, slug)
    record = await _answer(request, "accept", record.slug, identity)
    return view(request, record, OWNER)


@router.post("/api/rooms/{slug}/ownership/decline", status_code=204)
async def decline_ownership(slug: str, request: Request) -> Response:
    check_write(request)
    identity = signed_in(request)
    record = await _record(request, slug)
    await _answer(request, "decline", record.slug, identity)
    return Response(status_code=204)


async def _answer(request: Request, verb: str, slug: str, identity: Identity) -> RoomRecord:
    store = _store(request)
    call = store.accept_offer if verb == "accept" else store.decline_offer
    try:
        record = await asyncio.to_thread(call, slug, identity)
    except NoOffer:
        raise HTTPException(409, "There is no open offer for this room.") from None
    except NotOffered:
        raise HTTPException(403, "This room was not offered to you.") from None
    await _rooms(request).update(record)
    return record


# Validation and views


def view(request: Request, record: RoomRecord, access: str | None) -> dict[str, Any]:
    """The room as its viewer may see it. Only the owner and co-owners see the settings."""
    result: dict[str, Any] = {"slug": record.slug, "access": access}
    if access in MANAGERS:
        jira = record.jira
        offer = record.offer
        result["settings"] = {
            "owner": record.owner_label,
            "offer": {
                "provider": offer.provider,
                "identifier": offer.identifier,
                "expires_at": offer.expires_at.isoformat(timespec="seconds"),
            }
            if offer
            else None,
            "scale": record.scale.to_dict(),
            "timer_seconds": number(record.timer_seconds),
            "sound": record.sound,
            "auto_reveal": record.auto_reveal,
            "delegates": [d.to_dict() for d in record.delegates],
            "queue_filter": record.queue_filter.to_dict(),
            "jira": {
                "available": request.app.state.settings.atlassian is not None,
                "connected": jira.connected,
                "email": jira.email,
                "connected_by": jira.connected_by,
                "site": {"cloud_id": jira.cloud_id, "name": jira.site_name, "url": jira.site_url}
                if jira.has_board
                else None,
                "board": {"id": jira.board_id, "name": jira.board_name} if jira.has_board else None,
            },
        }
    return result


def offer_for(record: RoomRecord, identity: Identity | None) -> dict[str, str] | None:
    """What the offered account sees of an open offer: who it is from."""
    return {"from": record.owner_label} if record.offered_to(identity) else None


def queue_filter(value: Any) -> QueueFilter:
    try:
        return QueueFilter.from_dict(value)
    except FilterError as err:
        raise HTTPException(422, str(err)) from None


def _slug(value: Any) -> str:
    if not isinstance(value, str) or not SLUG.match(value):
        raise HTTPException(
            422,
            "A short name is 1 to 40 lowercase letters, digits or hyphens,"
            " starting with a letter or digit.",
        )
    if value.startswith(DEMO_PREFIX):
        raise HTTPException(422, f"Short names starting with {DEMO_PREFIX} are kept for demos.")
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
            raise HTTPException(422, "Each delegate is {provider, identifier, role}.")
        provider, identifier = entry.get("provider"), entry.get("identifier")
        role = entry.get("role", ROLES[0])
        if role not in ROLES:
            raise HTTPException(422, "A delegate's role is facilitator or co_owner.")
        if not isinstance(identifier, str):
            raise HTTPException(422, "Each delegate needs an email or GitHub username.")
        identifier = identifier.strip()
        if provider == "google" and EMAIL.match(identifier):
            found.append(Delegate("google", identifier.lower(), role))
        elif provider == "github" and GITHUB_LOGIN.match(identifier):
            found.append(Delegate("github", identifier.lower(), role))
        else:
            raise HTTPException(422, f"{identifier!r} is not a valid {provider} delegate.")
    return found
