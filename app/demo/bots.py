"""Bot players for demo rooms.

A bot is an ordinary connection to its live room: it reads only its own snapshots
from its outbox and sends the same commands a browser would. The room task stays
the only writer, and the bot learns other players' cards only after reveal, like
anyone else.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import random
from typing import Any

from app.room.live import Connection, LiveRoom

QUESTION = 0.06  # how often a bot plays "?"
COFFEE = 0.08  # how often a bot takes a coffee break before voting
SIZES = 6  # tickets "really" are one of the first few numeric cards


def ticket_size(key: str, numeric_cards: int) -> int:
    """The index of the numeric card a ticket "really" is: the same for every bot."""
    digest = hashlib.sha256(key.encode()).digest()
    return digest[0] % max(1, min(SIZES, numeric_cards))


class BotMind:
    """How one bot picks a card: near the ticket's size, shifted by its habit."""

    def __init__(self, name: str, bias: int, rng: random.Random) -> None:
        self.name = name
        self.bias = bias  # -1 guesses low, +1 guesses high
        self.rng = rng

    def choose(self, cards: list[dict[str, Any]], key: str) -> str:
        numeric = [c["label"] for c in cards if c["value"] is not None]
        question = next((c["label"] for c in cards if c["label"] == "?"), None)
        if not numeric or (question and self.rng.random() < QUESTION):
            return question or cards[0]["label"]
        size = ticket_size(key, len(numeric))
        index = size + self.bias + self.rng.choice((-1, 0, 0, 0, 1))
        index = max(0, min(len(numeric) - 1, index, size + 2))
        return numeric[max(index, size - 2)]

    def wants_coffee(self) -> bool:
        return self.rng.random() < COFFEE


class Bot:
    """Runs one bot against a live room until its task is cancelled."""

    def __init__(
        self,
        live: LiveRoom,
        mind: BotMind,
        delay: tuple[float, float],
    ) -> None:
        self.live = live
        self.mind = mind
        self.delay = delay
        self.player_id = "bot-" + mind.name.lower()
        self.conn: Connection | None = None
        self._latest: dict[str, Any] | None = None
        self._acting: asyncio.Task | None = None
        self._done_round: tuple[str, int] | None = None
        self._seen_vote: tuple[str, int] | None = None  # the round our vote was last seen in
        self._generation = 0
        self._was_voting = True
        self.removed = False  # a facilitator took it off the table; it stays off

    async def run(self) -> None:
        conn = self.live.connect(None, (self.player_id, self.mind.name), bot=True)
        self.conn = conn
        try:
            while True:
                message = await conn.outbox.get()
                if message is None:
                    return
                kind = message.get("type")
                if kind == "check_in":
                    self.live.submit(conn, {"type": "check_in"})
                elif kind == "state":
                    self._see(message)
        finally:
            if self._acting is not None:
                self._acting.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._acting
            self.live.disconnect(conn)

    def _round(self, snap: dict[str, Any]) -> tuple[str, int] | None:
        ticket = snap.get("ticket")
        return None if ticket is None else (ticket["key"], self._generation)

    def _see(self, snap: dict[str, Any]) -> None:
        self._latest = snap
        self.removed = snap["you"]["removed"]
        voting = snap["round"]["state"] == "voting"
        if voting and not self._was_voting:  # a restart, or the next ticket
            self._generation += 1
            self._done_round = None
        self._was_voting = voting
        you = snap["you"]
        round_ = self._round(snap)
        if not voting or round_ is None or not you["seated"] or you["sitting_out"]:
            return
        if you["vote"] is not None:
            self._seen_vote = round_
            return
        if round_ == self._seen_vote:
            # Our vote was counted this round and is gone now: a reset. Vote again.
            self._seen_vote = self._done_round = None
        if self._done_round is not None or self._acting is not None:
            return
        self._done_round = round_
        self._acting = asyncio.create_task(self._act(round_))

    async def _act(self, round_: tuple[str, int]) -> None:
        try:
            await self._pause()
            if self.mind.wants_coffee() and self._still(round_):
                self.live.submit(self.conn, {"type": "break", "on": True})
                await self._pause(2)
            if self._still(round_):
                card = self.mind.choose(self._latest["scale"]["cards"], round_[0])
                self.live.submit(self.conn, {"type": "vote", "card": card})
        finally:
            self._acting = None

    def _still(self, round_: tuple[str, int]) -> bool:
        snap = self._latest
        return (
            snap is not None
            and snap["round"]["state"] == "voting"
            and self._round(snap) == round_
            and snap["you"]["seated"]
        )

    async def _pause(self, factor: float = 1) -> None:
        low, high = self.delay
        await asyncio.sleep(self.mind.rng.uniform(low, high) * factor)
