"""Demo rooms: one private room per visitor, in memory only, with bots and a sample backlog.

Each demo room is a live room like any other, built from a record that is never
stored. Its backlog and its point writes go to its own copy of the sample backlog,
so nothing reaches Jira. It ends when no person has been connected for
DEMO_IDLE_SECONDS; its bots never keep it alive.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import secrets
import string

from fastapi import APIRouter, HTTPException, Request

from app.demo.backlog import SAMPLE_BACKLOG
from app.demo.bots import Bot, BotMind
from app.jira.fake import FakeJira
from app.room.live import LiveRoom
from app.room.ports import Clock
from app.room.room import Room
from app.store.rooms import RoomRecord
from app.web import check_write

PREFIX = "demo-"
MAX_DEMO_ROOMS = 20
MAX_BOTS = 8
DEMO_IDLE_SECONDS = 30 * 60
BOT_DELAY = (2.0, 7.0)  # seconds before a bot plays, after a round opens

# The team every demo room starts with, and the names Add a bot draws from next.
# The bias is each bot's habit: -1 guesses low, +1 high.
TEAM = [("Ada", 0), ("Bo", 1), ("Cleo", -1), ("Dev", 0)]
EXTRA = [("Eli", 1), ("Fran", -1), ("Gus", 0), ("Hana", 1), ("Ivo", -1), ("Juno", 0)]
EXTRA += [("Kai", 1), ("Lou", 0)]

_ALPHABET = string.ascii_lowercase + string.digits


class DemoFull(Exception):
    pass


class _Demo:
    def __init__(self, live: LiveRoom) -> None:
        self.live = live
        self.bots: dict[str, tuple[Bot, asyncio.Task]] = {}
        self.used: set[str] = set()


class DemoRooms:
    def __init__(self, clock: Clock, delay: tuple[float, float] = BOT_DELAY) -> None:
        self.clock = clock
        self.delay = delay
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
        if len(self._demos) >= MAX_DEMO_ROOMS:
            raise DemoFull
        slug = PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(8))
        while slug in self._demos:
            slug = PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(8))
        record = RoomRecord(slug, ("demo", slug), "Demo", sound=True)
        backlog = FakeJira(SAMPLE_BACKLOG)
        room = Room([], clock=self.clock, scale=record.scale, sound=True)
        live = LiveRoom(
            record, room, backlog, self.clock, backlog, demo=True, idle_seconds=DEMO_IDLE_SECONDS
        )
        live._on_idle = self._end
        demo = self._demos[slug] = _Demo(live)
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
        raise HTTPException(503, "All the demo rooms are in use. Try again later.") from None
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
