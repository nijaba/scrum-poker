"""The player cookie: a name and a random ID, kept for a year. Players never sign in.

The cookie is HttpOnly and set by the server, so `Secure` is decided in one
place: on whenever APP_BASE_URL is not localhost.
"""

from __future__ import annotations

import base64
import binascii
import json
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

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
