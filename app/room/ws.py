"""The WebSocket endpoint for players and facilitators.

The player cookie seats the browser. The session cookie, when it belongs to the
room's owner or a delegate, gives the session controls.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.players import COOKIE, decode_player
from app.room.live import Connection, RoomRegistry

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
MAX_MESSAGE = 16_384
CLOSE_NO_ROOM = 4404

router = APIRouter()


@router.websocket("/ws/rooms/{slug}")
async def room_socket(websocket: WebSocket, slug: str) -> None:
    store = websocket.app.state.store
    current = await asyncio.to_thread(store.resolve, slug) if SLUG.match(slug) else None
    record = await asyncio.to_thread(store.get, current) if current else None
    await websocket.accept()
    if record is None:
        # Accept first: a socket refused before it is accepted reaches the browser as
        # close code 1006, which looks like a dropped connection and is retried forever.
        await websocket.close(code=CLOSE_NO_ROOM)
        return

    registry: RoomRegistry = websocket.app.state.rooms
    live = await registry.get(record)
    account = websocket.app.state.auth.identity(websocket.cookies)
    player = decode_player(websocket.cookies.get(COOKIE))
    conn = live.connect(account, None if player is None else (player.id, player.name))
    sender = asyncio.create_task(_send_loop(websocket, conn))
    try:
        while True:
            text = await websocket.receive_text()
            data = _parse(text)
            if data is None:
                conn.send({"type": "error", "code": "invalid_message", "message": "Bad message."})
                continue
            live.submit(conn, data)
    except WebSocketDisconnect:
        pass
    finally:
        live.disconnect(conn)
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await sender


async def _send_loop(websocket: WebSocket, conn: Connection) -> None:
    while True:
        message = await conn.outbox.get()
        if message is None:
            return
        if message.get("type") == "_close":
            await websocket.close(code=message["code"])
            return
        await websocket.send_json(message)


def _parse(text: str) -> dict | None:
    if len(text) > MAX_MESSAGE:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
