"""The player cookie: a name and a random ID, kept for a year. Players never sign in.

The cookie is HttpOnly and set by the server, so `Secure` is decided in one
place: on whenever APP_BASE_URL is not localhost.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import re
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.room.errors import CommandError
from app.web import check_write

COOKIE = "sp_player"
MAX_AGE = 365 * 24 * 60 * 60
MAX_NAME = 40

router = APIRouter()


@dataclass(frozen=True)
class Player:
    id: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name}


def encode_player(player: Player) -> str:
    raw = json.dumps(player.to_dict(), separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_player(value: str | None) -> Player | None:
    """The player in a cookie value, or None if it is missing or malformed."""
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        data = json.loads(raw)
    except (binascii.Error, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    pid, name = data.get("id"), data.get("name")
    if not isinstance(pid, str) or not 0 < len(pid) <= 64:
        return None
    if not isinstance(name, str) or not 0 < len(name) <= MAX_NAME:
        return None
    return Player(pid, name)


@router.get("/api/player")
async def get_player(request: Request) -> dict[str, str]:
    player = decode_player(request.cookies.get(COOKIE))
    if player is None:
        raise HTTPException(404, "No player cookie.")
    return player.to_dict()


@router.post("/api/player")
async def set_player(request: Request) -> JSONResponse:
    """Set or change the player's name. An existing ID is kept."""
    check_write(request)
    try:
        body: Any = await request.json()
    except ValueError:
        body = None
    name = body.get("name") if isinstance(body, dict) else None
    if not isinstance(name, str) or not 0 < len(name.strip()) <= MAX_NAME:
        raise HTTPException(422, f"A name is 1 to {MAX_NAME} characters.")

    existing = decode_player(request.cookies.get(COOKIE))
    player = Player(existing.id if existing else secrets.token_urlsafe(16), name.strip())
    return _with_cookie(request, player)


def _with_cookie(request: Request, player: Player) -> JSONResponse:
    """The player as JSON, with the cookie that remembers them for a year."""
    response = JSONResponse(player.to_dict())
    response.set_cookie(
        COOKIE,
        encode_player(player),
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.secure_cookies,
    )
    return response


@router.delete("/api/player", status_code=204)
async def forget_player(request: Request) -> Response:
    """Forget the name and ID, as a player logging out does. The next name is a new player."""
    check_write(request)
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE, httponly=True, samesite="lax", secure=request.app.state.settings.secure_cookies
    )
    return response


SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


async def _live_room(request: Request, slug: str):
    """The room's live session, None when it has none running; 404 for no such room."""
    app = request.app
    demo = app.state.demo
    live = demo.get(slug) if demo is not None else None
    if live is None:
        store = app.state.store
        current = await asyncio.to_thread(store.resolve, slug) if SLUG.match(slug) else None
        if current is None:
            raise HTTPException(404, "There is no room with that name.")
        live = app.state.rooms.running(current)
    return live


@router.post("/api/rooms/{slug}/rename")
async def rename_in_room(slug: str, request: Request) -> JSONResponse:
    """Change this browser's player name, keeping the seat (design.md, "The menu behind your
    name"). Like leaving, a web request, so it works whatever state the socket is in."""
    check_write(request)
    try:
        body: Any = await request.json()
    except ValueError:
        body = None
    name = body.get("name") if isinstance(body, dict) else None
    if not isinstance(name, str) or not 0 < len(name.strip()) <= MAX_NAME:
        raise HTTPException(422, f"A name is 1 to {MAX_NAME} characters.")
    player = decode_player(request.cookies.get(COOKIE))
    if player is None:
        raise HTTPException(401, "Join a room first.")
    live = await _live_room(request, slug)
    if live is not None:
        try:
            await live.rename(player.id, name)
        except CommandError as err:
            status = 409 if err.code == "name_taken" else 422
            raise HTTPException(status, err.message) from None
    return _with_cookie(request, Player(player.id, name.strip()))


@router.post("/api/rooms/{slug}/leave", status_code=204)
async def leave_room(slug: str, request: Request) -> Response:
    """Take this browser's player off the room's table, as Log out does.

    A web request, not a socket message, so it works when the room's socket has dropped
    (a phone waking up, a network blip). Nothing to do without a player cookie or a
    running session; a session is never started just to leave it.
    """
    check_write(request)
    live = await _live_room(request, slug)
    player = decode_player(request.cookies.get(COOKIE))
    if live is not None and player is not None:
        live.leave(player.id)
    return Response(status_code=204)
