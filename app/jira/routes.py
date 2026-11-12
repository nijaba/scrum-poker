"""Connecting a room to Jira, and choosing its site and board. All of it is owner-only.

The consent flow is Atlassian's OAuth 2.0 authorization-code grant (3LO). Its
token calls send JSON, as Atlassian documents, through JiraService.
"""

from __future__ import annotations

import asyncio
import secrets
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.auth.access import OWNER
from app.jira.client import JiraError, JiraService
from app.rooms_api import json_body, view
from app.store.rooms import RoomRecord
from app.web import check_write

STATE_COOKIE = "sp_jira_oauth"
STATE_MAX_AGE = 10 * 60

router = APIRouter()


def _service(request: Request) -> JiraService:
    return request.app.state.jira


def _states(request: Request) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(request.app.state.settings.session_secret, salt="jira-oauth")


async def owner_record(request: Request, slug: str) -> RoomRecord:
    """The room, if the signed-in account owns it: 401 signed out, 403 not the owner."""
    identity = request.app.state.auth.identity(request.cookies)
    if identity is None:
        raise HTTPException(401, "Sign in first.")
    store = request.app.state.store
    current = await asyncio.to_thread(store.resolve, slug)
    record = await asyncio.to_thread(store.get, current) if current else None
    if record is None:
        raise HTTPException(404, "No such room.")
    if record.access(identity) != OWNER:
        raise HTTPException(403, "Only the room's owner can change its Jira connection.")
    return record


def _http_error(err: JiraError) -> HTTPException:
    status = {
        "jira_unavailable": 404,
        "jira_not_connected": 409,
        "jira_reconnect": 409,
        "jira_unreachable": 502,
        "jira_error": 502,
    }.get(err.code, 422)
    return HTTPException(status, err.message)


# The consent flow


@router.get("/auth/atlassian/login")
async def login(request: Request, room: str) -> Response:
    record = await owner_record(request, room)
    config = _service(request).config if request.app.state.settings.atlassian else None
    if config is None:
        raise HTTPException(404, "Jira is not set up on this server.")
    state = secrets.token_urlsafe(24)
    query = urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": config.client_id,
            "scope": config.scope,
            "redirect_uri": config.callback_url,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
    )
    response = RedirectResponse(f"{config.authorize_url}?{query}", status_code=303)
    value = _states(request).dumps({"s": state, "room": record.slug})
    request.app.state.auth.set_cookie(response, STATE_COOKIE, value, STATE_MAX_AGE)
    return response


@router.get("/auth/atlassian/callback")
async def callback(
    request: Request, code: str | None = None, state: str | None = None, error: str | None = None
) -> Response:
    try:
        saved = _states(request).loads(request.cookies.get(STATE_COOKIE, ""), max_age=STATE_MAX_AGE)
    except BadSignature:
        return _failed("Connecting Jira took too long or started in another browser. Try again.")
    if not state or saved.get("s") != state:
        return _failed("Connecting Jira could not be checked. Try again.")
    record = await owner_record(request, saved["room"])
    settings_page = f"/r/{record.slug}/settings"
    if error or not code:
        return _done(f"{settings_page}?jira=denied")
    try:
        record = await _service(request).connect(record.slug, code)
    except JiraError as err:
        return _failed(err.message)
    await request.app.state.rooms.update(record)
    return _done(f"{settings_page}?jira=connected")


def _done(location: str) -> Response:
    response = RedirectResponse(location, status_code=303)
    response.delete_cookie(STATE_COOKIE)
    return response


def _failed(message: str) -> HTMLResponse:
    safe = message.replace("&", "&amp;").replace("<", "&lt;")
    response = HTMLResponse(
        "<!doctype html><meta charset=utf-8><title>Jira not connected</title>"
        f"<p>{safe}</p><p><a href='/'>Back to Scrum poker</a></p>",
        status_code=400,
    )
    response.delete_cookie(STATE_COOKIE)
    return response


# Site and board


@router.get("/api/rooms/{slug}/jira/sites")
async def sites(slug: str, request: Request) -> list[dict[str, str]]:
    record = await owner_record(request, slug)
    try:
        return await _service(request).sites(record.slug)
    except JiraError as err:
        raise _http_error(err) from err


@router.get("/api/rooms/{slug}/jira/boards")
async def boards(slug: str, cloud_id: str, request: Request) -> list[dict[str, Any]]:
    record = await owner_record(request, slug)
    try:
        return await _service(request).boards(record.slug, cloud_id)
    except JiraError as err:
        raise _http_error(err) from err


@router.put("/api/rooms/{slug}/jira/board")
async def choose_board(slug: str, request: Request) -> dict[str, Any]:
    check_write(request)
    record = await owner_record(request, slug)
    body = await json_body(request)
    cloud_id, board_id = body.get("cloud_id"), body.get("board_id")
    if not isinstance(cloud_id, str) or isinstance(board_id, bool) or not isinstance(board_id, int):
        raise HTTPException(422, "Send cloud_id (text) and board_id (a number).")
    service = _service(request)
    try:
        site = next(
            (s for s in await service.sites(record.slug) if s["cloud_id"] == cloud_id), None
        )
        if site is None:
            raise HTTPException(422, "This Jira connection cannot reach that site.")
        board = next(
            (b for b in await service.boards(record.slug, cloud_id) if b["id"] == board_id), None
        )
    except JiraError as err:
        raise _http_error(err) from err
    if board is None:
        raise HTTPException(
            422, "That board is not on the site, or not visible to this connection."
        )
    store = request.app.state.store
    record = await asyncio.to_thread(
        store.set_jira_board,
        record.slug,
        cloud_id,
        site["url"],
        site["name"],
        board_id,
        board["name"],
    )
    await request.app.state.rooms.update(record)
    return view(request, record, OWNER)


@router.delete("/api/rooms/{slug}/jira", status_code=204)
async def disconnect(slug: str, request: Request) -> Response:
    check_write(request)
    record = await owner_record(request, slug)
    record = await asyncio.to_thread(request.app.state.store.clear_jira, record.slug)
    _service(request).forget(record.slug)
    await request.app.state.rooms.update(record)
    return Response(status_code=204)
