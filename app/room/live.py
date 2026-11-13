"""Live rooms: one asyncio task per room owns its state and reads commands from a queue.

Connections never touch the room. They put commands on the room's inbox and read
their own snapshots from an outbox that the room task fills. Settings saved by the
owner arrive the same way, so the task stays the only writer.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import logging
from dataclasses import dataclass, field
from typing import Any

from app.auth.identity import Identity
from app.room.errors import CommandError
from app.room.ports import BacklogError, BacklogSource, Clock, PointsWriteError, PointsWriter
from app.room.room import Room
from app.store.rooms import RoomRecord

log = logging.getLogger(__name__)

PLAYER = "player"
FACILITATOR = "facilitator"

# Close codes the browser understands.
CLOSE_DELETED = 4410

# A session ends when nobody has been connected for this long; the next one reloads the backlog.
IDLE_SECONDS = 15 * 60

# Problems with the room's Jira connection: every facilitator hears about them, not just
# the one who confirmed, because only the owner can fix them.
CONNECTION_CODES = {"jira_not_connected", "jira_reconnect", "jira_no_board", "jira_board_missing"}

PLAYER_COMMANDS = {"join", "vote", "withdraw", "check_in", "sit_out", "sit_in", "leave"}
# Session controls, for the owner and delegates. Room settings (scale, saved timer
# and sound, delegates) change only through the owner's settings API.
FACILITATOR_COMMANDS = {
    "reveal",
    "restart",
    "confirm",
    "skip",
    "rewind",
    "reset",
    "start_countdown",
    "stop_countdown",
    "set_timer",  # this session only
    "set_sound",  # this session only
    "set_auto_reveal",  # this session only
    "remove_player",
    "jump",
    "reload_backlog",  # after a failed load, once the owner has fixed the connection
}

_ids = itertools.count(1)


@dataclass(eq=False)
class Connection:
    """One browser's WebSocket, as the room task sees it."""

    account: Identity | None = None  # the signed-in owner or delegate, if any
    id: int = field(default_factory=lambda: next(_ids))
    outbox: asyncio.Queue = field(default_factory=asyncio.Queue)
    player_id: str | None = None
    name: str | None = None

    def send(self, message: dict[str, Any] | None) -> None:
        """Queue a message. None ends the connection's sender."""
        self.outbox.put_nowait(message)


@dataclass
class _Connect:
    conn: Connection


@dataclass
class _Disconnect:
    conn: Connection


@dataclass
class _Message:
    conn: Connection
    data: dict[str, Any]


@dataclass
class _Tick:
    pass


@dataclass
class _Update:
    record: RoomRecord
    moved_from: str | None


@dataclass
class _Delete:
    pass


@dataclass
class _Load:
    pass


@dataclass
class _Close:
    pass


class LiveRoom:
    def __init__(
        self,
        record: RoomRecord,
        room: Room,
        writer: PointsWriter,
        clock: Clock,
        backlog: BacklogSource | None = None,
    ) -> None:
        self.slug = record.slug
        self.closed = False
        self._record = record
        self._room = room
        self._writer = writer
        self._backlog = backlog
        self._clock = clock
        self._backlog_state: dict[str, Any] = {"state": "loading", "code": None, "message": None}
        self._empty_since: float | None = clock.now()
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._conns: list[Connection] = []
        self._task: asyncio.Task | None = None
        self._timer: asyncio.Task | None = None
        self._timer_deadline: float | None = None

    # Called from connection handlers and the settings API. These only enqueue.

    def start(self) -> None:
        if self._backlog is not None:
            self._inbox.put_nowait(_Load())
        else:
            self._backlog_state = {"state": "ready", "code": None, "message": None}
        self._task = asyncio.create_task(self._run(), name=f"room:{self.slug}")

    def idle_expired(self) -> bool:
        """Nobody has been connected for IDLE_SECONDS, and nothing is waiting to be handled."""
        return (
            self._empty_since is not None
            and self._inbox.empty()
            and self._clock.now() >= self._empty_since + IDLE_SECONDS
        )

    def close(self) -> None:
        """End the session. The registry has already forgotten this room."""
        self.closed = True
        self._inbox.put_nowait(_Close())

    def connect(
        self, account: Identity | None = None, player: tuple[str, str] | None = None
    ) -> Connection:
        """Register a connection. With a player (from the player cookie) it is seated."""
        conn = Connection(account=account)
        if player is not None:
            conn.player_id, conn.name = player
        self._inbox.put_nowait(_Connect(conn))
        return conn

    def submit(self, conn: Connection, data: dict[str, Any]) -> None:
        self._inbox.put_nowait(_Message(conn, data))

    def disconnect(self, conn: Connection) -> None:
        self._inbox.put_nowait(_Disconnect(conn))

    def update(self, record: RoomRecord, moved_from: str | None = None) -> None:
        self.slug = record.slug
        self._inbox.put_nowait(_Update(record, moved_from))

    def delete(self) -> None:
        self._inbox.put_nowait(_Delete())

    async def stop(self) -> None:
        for task in (self._timer, self._task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    # The room task

    async def _run(self) -> None:
        while True:
            command = await self._inbox.get()
            if isinstance(command, _Delete):
                self._close_all()
                return
            if isinstance(command, _Close):
                if self._timer is not None:
                    self._timer.cancel()
                return
            try:
                changed = await self._handle(command)
            except CommandError as err:
                if isinstance(command, _Message):
                    command.conn.send({"type": "error", "code": err.code, "message": err.message})
                changed = False
            except Exception:  # keep the room alive whatever one command does
                log.exception("room %s: command failed", self.slug)
                changed = False
            self._schedule_timer()
            if changed:
                self._broadcast()
            if isinstance(command, _Tick) and self.idle_expired() and self._on_idle:
                self._on_idle(self)

    _on_idle = None  # set by the registry: called when the session ends for being idle

    async def _handle(self, command: Any) -> bool:
        room = self._room
        if isinstance(command, _Tick):
            return room.tick()
        if isinstance(command, _Load):
            return await self._load()
        if isinstance(command, _Update):
            return self._apply(command)
        if isinstance(command, _Connect):
            conn = command.conn
            self._conns.append(conn)
            self._empty_since = None
            if conn.player_id is not None:
                try:
                    room.join(conn.player_id, conn.name)
                except CommandError as err:
                    # The saved name is taken (or bad): say why, then show the room unseated.
                    conn.player_id = conn.name = None
                    conn.send({"type": "error", "code": err.code, "message": err.message})
                else:
                    return True
            conn.send(self._snapshot(conn))
            return False
        if isinstance(command, _Disconnect):
            conn = command.conn
            if conn in self._conns:
                self._conns.remove(conn)
            if not self._conns:
                self._empty_since = self._clock.now()
            conn.send(None)
            if conn.player_id and not any(c.player_id == conn.player_id for c in self._conns):
                room.set_connected(conn.player_id, False)
                return True
            return False
        return await self._message(command.conn, command.data)

    def _apply(self, command: _Update) -> bool:
        """Saved settings reach the session. Only fields that changed are applied, so a
        delegate list edit keeps the session's own timer and sound."""
        old, new = self._record, command.record
        self._record = new
        board_changed = (new.jira.cloud_id, new.jira.board_id) != (
            old.jira.cloud_id,
            old.jira.board_id,
        )
        if self._backlog is not None and (
            board_changed or (new.jira != old.jira and self._backlog_state["state"] != "ready")
        ):
            self._inbox.put_nowait(_Load())
        if new.scale != old.scale:
            self._room.set_scale(new.scale)
        if new.timer_seconds != old.timer_seconds:
            self._room.set_timer(new.timer_seconds)
        if new.sound != old.sound:
            self._room.set_sound(new.sound)
        if new.auto_reveal != old.auto_reveal:
            self._room.set_auto_reveal(new.auto_reveal)
        if command.moved_from is not None:
            for conn in self._conns:
                conn.send({"type": "moved", "slug": new.slug})
        return True  # roles may have changed with the delegates

    def _role(self, conn: Connection) -> tuple[str, str | None]:
        access = self._record.access(conn.account)
        return (FACILITATOR if access else PLAYER), access

    async def _message(self, conn: Connection, data: dict[str, Any]) -> bool:
        room = self._room
        kind = data.get("type")
        if kind not in PLAYER_COMMANDS and kind not in FACILITATOR_COMMANDS:
            raise CommandError("unknown_command", "Unknown command.")
        if kind in FACILITATOR_COMMANDS and self._role(conn)[0] != FACILITATOR:
            raise CommandError("forbidden", "Only a facilitator can do that.")

        if kind == "join":
            seat = room.join(data.get("player_id", conn.player_id), data.get("name", conn.name))
            conn.player_id, conn.name = seat.player_id, seat.name
        elif kind == "check_in":
            if conn.player_id is None or conn.name is None:
                raise CommandError("not_seated", "Join the room first.")
            room.check_in(conn.player_id, conn.name)
        elif kind == "vote":
            room.vote(conn.player_id, data.get("card"))
        elif kind == "withdraw":
            room.withdraw(conn.player_id)
        elif kind == "sit_out":
            room.sit_out(conn.player_id)
        elif kind == "sit_in":
            room.sit_in(conn.player_id)
        elif kind == "leave":
            room.leave(conn.player_id)
        elif kind == "reveal":
            room.reveal()
        elif kind == "restart":
            room.restart()
        elif kind == "confirm":
            await self._confirm(conn, data.get("points"))
        elif kind == "skip":
            room.skip()
        elif kind == "rewind":
            room.rewind()
        elif kind == "jump":
            room.jump(data.get("key"))
        elif kind == "remove_player":
            room.remove(data.get("player_id"))
        elif kind == "reset":
            room.reset()
            for c in self._conns:
                c.send({"type": "check_in"})
        elif kind == "start_countdown":
            room.start_countdown(data.get("seconds"))
        elif kind == "stop_countdown":
            room.stop_countdown()
        elif kind == "set_timer":
            room.set_timer(data.get("seconds"))
        elif kind == "set_sound":
            room.set_sound(data.get("on"))
        elif kind == "set_auto_reveal":
            room.set_auto_reveal(data.get("on"))
        elif kind == "reload_backlog":
            if self._backlog_state["state"] == "ready":
                raise CommandError("backlog_loaded", "The backlog is already loaded.")
            return await self._load()
        return True

    async def _load(self) -> bool:
        """Load the board backlog through the room's Jira connection. A failure is shown."""
        self._backlog_state = {"state": "loading", "code": None, "message": None}
        self._broadcast()
        try:
            backlog = await self._backlog.load_backlog(self._record.slug)
        except BacklogError as err:
            self._backlog_state = {"state": "error", "code": err.code, "message": err.message}
            return True
        except Exception:
            log.exception("room %s: loading the backlog failed", self.slug)
            self._backlog_state = {
                "state": "error",
                "code": "backlog_failed",
                "message": "The backlog could not load. Try again.",
            }
            return True
        self._room.set_backlog(backlog)
        self._backlog_state = {"state": "ready", "code": None, "message": None}
        return True

    async def _confirm(self, conn: Connection, value: Any) -> None:
        """Write to Jira first; the room advances only once the write is accepted."""
        room = self._room
        points = room.points_for(value)
        ticket = room.queue.current
        try:
            await self._writer.write_points(self._record.slug, ticket.key, points)
        except PointsWriteError as err:
            message = err.message or "Jira did not accept the points."
            if err.code in CONNECTION_CODES:
                for other in self._conns:
                    if other is not conn and self._role(other)[0] == FACILITATOR:
                        other.send({"type": "error", "code": err.code, "message": message})
            raise CommandError(err.code, message) from err
        except Exception as err:
            log.warning("room %s: writing %s failed: %r", self.slug, ticket.key, err)
            raise CommandError("jira_unreachable", "Could not reach Jira. Try again.") from err
        room.record_estimate(points)

    def _broadcast(self) -> None:
        for conn in self._conns:
            conn.send(self._snapshot(conn))

    def _snapshot(self, conn: Connection) -> dict[str, Any]:
        snapshot = self._room.snapshot_for(conn.player_id)
        role, access = self._role(conn)
        snapshot["you"]["role"] = role
        snapshot["you"]["access"] = access
        snapshot["you"]["account_name"] = conn.account.name if conn.account else None
        snapshot["room"] = {"slug": self._record.slug}
        snapshot["backlog"] = dict(self._backlog_state)
        if role == FACILITATOR:  # the session summary is for facilitators only
            snapshot["summary"] = self._room.summary()
        return snapshot

    def _close_all(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        for conn in self._conns:
            conn.send({"type": "deleted"})
            conn.send({"type": "_close", "code": CLOSE_DELETED})
        self._conns.clear()

    def _schedule_timer(self) -> None:
        deadlines = [self._room.next_deadline()]
        if self._empty_since is not None:
            deadlines.append(self._empty_since + IDLE_SECONDS)
        deadline = min((d for d in deadlines if d is not None), default=None)
        if deadline == self._timer_deadline and (self._timer is None or not self._timer.done()):
            return
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._timer_deadline = deadline
        if deadline is not None:
            self._timer = asyncio.create_task(self._wake_at(deadline))

    async def _wake_at(self, deadline: float) -> None:
        await self._clock.sleep_until(deadline)
        self._inbox.put_nowait(_Tick())


class RoomRegistry:
    """The live rooms in this process, created on first use from their stored record."""

    def __init__(self, backlog: BacklogSource, writer: PointsWriter, clock: Clock) -> None:
        self._backlog = backlog
        self._writer = writer
        self._clock = clock
        self._rooms: dict[str, LiveRoom] = {}
        self._lock = asyncio.Lock()

    async def get(self, record: RoomRecord) -> LiveRoom:
        """The room's live session, starting a new one if there is none or it went idle."""
        async with self._lock:
            live = self._rooms.get(record.slug)
            if live is not None and (live.closed or live.idle_expired()):
                self._end(live)
                live = None
            if live is None:
                room = Room(
                    [],
                    clock=self._clock,
                    scale=record.scale,
                    timer_seconds=record.timer_seconds,
                    sound=record.sound,
                    auto_reveal=record.auto_reveal,
                )
                live = LiveRoom(record, room, self._writer, self._clock, self._backlog)
                live._on_idle = self._end
                self._rooms[record.slug] = live
                live.start()
            return live

    def _end(self, live: LiveRoom) -> None:
        """Forget an idle session. Safe to call twice."""
        if self._rooms.get(live.slug) is live:
            del self._rooms[live.slug]
        if not live.closed:
            live.close()

    async def update(self, record: RoomRecord, moved_from: str | None = None) -> None:
        """Pass saved settings to the live room, if one is running. A rename moves it."""
        async with self._lock:
            live = self._rooms.pop(moved_from or record.slug, None)
            if live is None:
                return
            self._rooms[record.slug] = live
            live.update(record, moved_from)

    async def delete(self, slug: str) -> None:
        async with self._lock:
            live = self._rooms.pop(slug, None)
        if live is not None:
            live.delete()

    async def close(self) -> None:
        rooms, self._rooms = list(self._rooms.values()), {}
        for live in rooms:
            await live.stop()
