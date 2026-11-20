"""Demo rooms: one private room per visitor, in memory only, with bots and a sample backlog.

Each demo room is a live room like any other, built from a record that is never
stored. Its backlog and its point writes go to its own copy of the sample backlog,
so nothing reaches Jira. It ends when no person has been connected for its idle
time (DEMO_IDLE_SECONDS); its bots never keep it alive. At most DEMO_MAX_ROOMS run
at once.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import random
import secrets
import string
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config import DEFAULT_DEMO_IDLE_SECONDS, DEFAULT_DEMO_MAX_ROOMS
from app.demo.backlog import DemoBacklog
from app.demo.bots import Bot, BotMind
from app.room.errors import CommandError
from app.room.live import LiveRoom
from app.room.ports import BacklogError, Clock
from app.room.queue_filter import QueueFilter
from app.room.room import Room
from app.room.scales import Scale, number
from app.store.rooms import Delegate, JiraLink, RoomRecord
from app.web import check_write

PREFIX = "demo-"
MAX_DEMO_ROOMS = DEFAULT_DEMO_MAX_ROOMS
MAX_BOTS = 8
DEMO_IDLE_SECONDS = DEFAULT_DEMO_IDLE_SECONDS
FULL = (
    "Every demo table is taken: the bots are busy estimating someone else's backlog."
    " Grab a coffee and come back in a few minutes."
)
BOT_DELAY = (2.0, 7.0)  # seconds before a bot plays, after a round opens

# The team every demo room starts with, and the names Add a bot draws from next.
# The bias is each bot's habit: -1 guesses low, +1 high.
TEAM = [("Ada", 0), ("Bo", 1), ("Cleo", -1), ("Dev", 0)]
EXTRA = [("Eli", 1), ("Fran", -1), ("Gus", 0), ("Hana", 1), ("Ivo", -1), ("Juno", 0)]
EXTRA += [("Kai", 1), ("Lou", 0)]

_ALPHABET = string.ascii_lowercase + string.digits


class DemoFull(Exception):
    pass


# What a demo room's settings show for what it cannot do for real (design.md, "Demo rooms").
PRETEND_JIRA = JiraLink(
    token="demo",
    email="demo@example.com",
    cloud_id="demo",
    site_name="Demo Co",
    site_url="https://demo-co.example.com",
    board_id=1,
    board_name="SHOP board",
    connected_by="the demo",
)
SAMPLE_DELEGATE = Delegate("google", "dana@example.com")


class _Demo:
    def __init__(self, live: LiveRoom, record: RoomRecord, backlog: DemoBacklog) -> None:
        self.live = live
        self.record = record  # in memory only, like the room; changed by its settings page
        self.backlog = backlog
        self.bots: dict[str, tuple[Bot, asyncio.Task]] = {}
        self.used: set[str] = set()


class DemoRooms:
    def __init__(
        self,
        clock: Clock,
        delay: tuple[float, float] = BOT_DELAY,
        *,
        max_rooms: int = MAX_DEMO_ROOMS,
        idle_seconds: int = DEMO_IDLE_SECONDS,
    ) -> None:
        self.clock = clock
        self.delay = delay
        self.max_rooms = max_rooms
        self.idle_seconds = idle_seconds
        self.rng = random.Random()
        self._demos: dict[str, _Demo] = {}

    def get(self, slug: str) -> LiveRoom | None:
        demo = self._demos.get(slug)
        return demo.live if demo is not None else None

    def bot_tasks(self, slug: str) -> list[asyncio.Task]:
        demo = self._demos.get(slug)
        return [] if demo is None else [task for _, task in demo.bots.values()]

    async def create(self) -> str:
        """Start a new demo room with its team of bots, and return its short name."""
        if len(self._demos) >= self.max_rooms:
            raise DemoFull
        slug = PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(8))
        while slug in self._demos:
            slug = PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(8))
        record = RoomRecord(
            slug,
            ("demo", slug),
            "Demo",
            sound=True,
            jira=PRETEND_JIRA,
            delegates=(SAMPLE_DELEGATE,),
        )
        holder: dict[str, _Demo] = {}
        backlog = DemoBacklog(lambda: holder["demo"].record.queue_filter)
        room = Room([], clock=self.clock, scale=record.scale, sound=True)
        live = LiveRoom(
            record, room, backlog, self.clock, backlog, demo=True, idle_seconds=self.idle_seconds
        )
        live._on_idle = self._end
        demo = self._demos[slug] = holder["demo"] = _Demo(live, record, backlog)
        live.start()
        for name, bias in TEAM:
            self._seat(demo, name, bias)
        return slug

    def add_bot(self, slug: str) -> str | None:
        """Seat one more bot, with a name not used in this room yet. None when full."""
        demo = self._demos[slug]
        seated = [b for b, task in demo.bots.values() if not task.done() and not b.removed]
        if len(seated) >= MAX_BOTS:
            return None
        for name, bias in TEAM + EXTRA:
            if name not in demo.used:
                self._seat(demo, name, bias)
                return name
        return None

    def record(self, slug: str) -> RoomRecord | None:
        demo = self._demos.get(slug)
        return demo.record if demo is not None else None

    def save(self, slug: str, **changes: Any) -> RoomRecord:
        """Change a demo room's settings, in memory, and pass them to its live room."""
        demo = self._demos[slug]
        demo.record = dataclasses.replace(demo.record, **changes)
        demo.live.update(demo.record)
        return demo.record

    def preview(self, slug: str, chosen: QueueFilter) -> list[dict[str, Any]]:
        return self._demos[slug].backlog.backlog(chosen)

    def _seat(self, demo: _Demo, name: str, bias: int) -> None:
        bot = Bot(demo.live, BotMind(name, bias, self.rng), self.delay)
        demo.used.add(name)
        demo.bots[name] = (bot, asyncio.create_task(bot.run(), name=f"bot:{name}"))

    def _end(self, live: LiveRoom) -> None:
        """The room went idle: forget it, close it and stop its bots."""
        demo = self._demos.get(live.slug)
        if demo is None or demo.live is not live:
            return
        del self._demos[live.slug]
        live.close()
        for _, task in demo.bots.values():
            task.cancel()

    async def close(self) -> None:
        demos, self._demos = list(self._demos.values()), {}
        for demo in demos:
            for _, task in demo.bots.values():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await demo.live.stop()


# The API

router = APIRouter()


def _demos(request: Request) -> DemoRooms:
    demos = request.app.state.demo
    if demos is None:
        raise HTTPException(404, "Demo rooms are off.")
    return demos


@router.post("/api/demo", status_code=201)
async def create_demo(request: Request) -> dict[str, str]:
    check_write(request)
    try:
        slug = await _demos(request).create()
    except DemoFull:
        raise HTTPException(503, FULL) from None
    return {"slug": slug}


@router.post("/api/demo/{slug}/bots", status_code=201)
async def add_bot(slug: str, request: Request) -> dict[str, str]:
    check_write(request)
    demos = _demos(request)
    if demos.get(slug) is None:
        raise HTTPException(404, "There is no demo room by that name.")
    name = demos.add_bot(slug)
    if name is None:
        raise HTTPException(409, f"A demo room has at most {MAX_BOTS} bots.")
    return {"name": name}


# Setting up a demo room (design.md, "Demo rooms"): anyone with the link, like the controls.
DEMO_SETTINGS = {"scale", "timer_seconds", "sound", "auto_reveal", "queue_filter"}


def settings_view(record: RoomRecord) -> dict[str, Any]:
    """A demo room's settings, in the shape a real room's settings page reads."""
    jira = record.jira
    return {
        "owner": "the demo",
        "offer": None,
        "scale": record.scale.to_dict(),
        "timer_seconds": number(record.timer_seconds),
        "sound": record.sound,
        "auto_reveal": record.auto_reveal,
        "delegates": [d.to_dict() for d in record.delegates],
        "queue_filter": record.queue_filter.to_dict(),
        "jira": {
            "available": True,
            "connected": True,
            "email": jira.email,
            "connected_by": jira.connected_by,
            "site": {"cloud_id": jira.cloud_id, "name": jira.site_name, "url": jira.site_url},
            "board": {"id": jira.board_id, "name": jira.board_name},
        },
    }


def _live_demo(request: Request, slug: str) -> RoomRecord:
    record = _demos(request).record(slug)
    if record is None:
        raise HTTPException(404, "There is no demo room by that name.")
    return record


@router.patch("/api/demo/{slug}/settings")
async def save_settings(slug: str, request: Request) -> dict[str, Any]:
    # Imported here: app.rooms_api imports this module for the demo name prefix.
    from app.rooms_api import _timer, json_body, queue_filter

    check_write(request)
    _live_demo(request, slug)
    body = await json_body(request)
    unknown = set(body) - DEMO_SETTINGS
    if unknown:
        raise HTTPException(
            422, f"A demo room cannot change {', '.join(sorted(unknown))}: a real room can."
        )
    changes: dict[str, Any] = {}
    try:
        if "scale" in body:
            changes["scale"] = Scale.from_dict(body["scale"])
    except CommandError as err:
        raise HTTPException(422, err.message) from None
    if "timer_seconds" in body:
        changes["timer_seconds"] = _timer(body["timer_seconds"])
    for name in ("sound", "auto_reveal"):
        if name in body:
            if not isinstance(body[name], bool):
                raise HTTPException(422, f"{name.replace('_', '-').capitalize()} is true or false.")
            changes[name] = body[name]
    if "queue_filter" in body:
        changes["queue_filter"] = queue_filter(body["queue_filter"])
    record = _demos(request).save(slug, **changes)
    return {"slug": slug, "access": None, "demo": True, "settings": settings_view(record)}


@router.post("/api/demo/{slug}/queue-preview")
async def demo_queue_preview(slug: str, request: Request) -> dict[str, Any]:
    from app.jira.routes import PREVIEW_LIMIT
    from app.rooms_api import json_body, queue_filter

    check_write(request)
    _live_demo(request, slug)
    chosen = queue_filter((await json_body(request)).get("queue_filter", {}))
    try:
        tickets = _demos(request).preview(slug, chosen)
    except BacklogError as err:
        raise HTTPException(422, err.message) from None
    queue = [t for t in tickets if chosen.estimated or t.get("story_points") is None]
    return {
        "count": len(queue),
        "total": len(tickets),
        "tickets": [
            {
                "key": t["key"],
                "summary": t["summary"],
                "type": t["type"],
                "status": t["status"],
                "estimate": t["story_points"],
                "url": t["url"],
            }
            for t in queue[:PREVIEW_LIMIT]
        ],
    }
