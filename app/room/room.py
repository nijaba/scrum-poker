"""One room's state and rules, with no I/O.

The live room task (`app.room.live`) is the only caller in the running app. It
checks roles; this class checks everything else.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.room.errors import CommandError
from app.room.ports import Clock
from app.room.queue import Queue
from app.room.round import REVEALED, VOTING, Round
from app.room.scales import Scale, fibonacci, number, parse_value

DEFAULT_TIMER = 30
MAX_TIMER = 3600
CHECK_IN_SECONDS = 5.0
MAX_NAME = 40
MAX_PLAYER_ID = 64
UP_NEXT = 5


@dataclass
class Seat:
    player_id: str
    name: str
    connected: bool = True
    sitting_out: bool = False  # in the room and watching, but not at the table
    on_break: bool = False  # asked for a coffee break; a signal, not a vote


class Room:
    def __init__(
        self,
        backlog: list[dict[str, Any]],
        *,
        clock: Clock,
        scale: Scale | None = None,
        timer_seconds: float = DEFAULT_TIMER,
        sound: bool = False,
        auto_reveal: bool = False,
        check_in_seconds: float = CHECK_IN_SECONDS,
        include_estimated: bool = False,
    ) -> None:
        self.clock = clock
        self.queue = Queue.from_backlog(backlog, include_estimated)
        self.scale = scale or fibonacci()
        self.next_scale: Scale | None = None
        self.timer_seconds = _seconds(timer_seconds)
        self.sound = sound
        self.auto_reveal = auto_reveal
        self.check_in_seconds = check_in_seconds
        self.seats: dict[str, Seat] = {}
        # Players who chose to sit out. Kept apart from the seats so a reset keeps it.
        self.sitting_out: set[str] = set()
        # Players a facilitator removed, until they join again: their screen says so.
        self.removed: set[str] = set()
        self.round = Round(self.scale)
        self.countdown_duration: float | None = None
        self.countdown_deadline: float | None = None
        self.time_up = False
        self.check_in_deadline: float | None = None

    def set_backlog(self, backlog: list[dict[str, Any]], include_estimated: bool = False) -> None:
        """Replace the queue with a freshly loaded backlog, and start a new round.
        The session's results carry over, so a reload never loses or double counts one."""
        self.queue = Queue.from_backlog(backlog, include_estimated, self.queue.kept())
        self._new_round()

    def can_reload(self) -> bool:
        """Between tickets: nobody has voted on the current one, or the queue is done."""
        return self.queue.finished or (self.round.state == VOTING and not self.round.votes)

    # Seats

    def join(self, player_id: str, name: str) -> Seat:
        """Seat a player, or update the name and mark them connected if already seated.

        A name held by another seat, at the table, watching or away, is refused, ignoring
        case and extra spaces, so everyone can tell who played what.
        """
        player_id, name = _identity(player_id, name)
        for other in self.seats.values():
            if other.player_id != player_id and _same_name(other.name, name):
                raise CommandError(
                    "name_taken",
                    f"Someone at the table is already called {other.name}. Choose another name.",
                )
        seat = self.seats.get(player_id)
        if seat is None:
            seat = self.seats[player_id] = Seat(player_id, name)
        seat.name = name
        seat.connected = True
        seat.sitting_out = player_id in self.sitting_out
        self.removed.discard(player_id)
        return seat

    def set_connected(self, player_id: str, connected: bool) -> None:
        seat = self.seats.get(player_id)
        if seat is not None:
            seat.connected = connected
            if not connected:
                self._auto_reveal()

    def sit_out(self, player_id: str) -> None:
        """Leave the table but stay in the room. The vote, if any, is dropped."""
        seat = self._require_seat(player_id)
        seat.sitting_out = True
        seat.on_break = False
        self.sitting_out.add(player_id)
        self.round.drop(player_id)
        self._auto_reveal()

    def sit_in(self, player_id: str) -> None:
        seat = self._require_seat(player_id)
        seat.sitting_out = False
        self.sitting_out.discard(player_id)

    def remove(self, player_id: Any) -> None:
        """A facilitator takes a player off the table. They can join again."""
        if not isinstance(player_id, str) or player_id not in self.seats:
            raise CommandError("not_seated", "That player is not in the room.")
        del self.seats[player_id]
        self.sitting_out.discard(player_id)
        self.removed.add(player_id)
        self.round.drop(player_id)
        self._auto_reveal()

    def leave(self, player_id: str | None) -> None:
        """A player leaves the table on their own, as on logging out. Nothing to undo if
        they had no seat; unlike a removal, their screen gets no notice."""
        if player_id is None or player_id not in self.seats:
            return
        del self.seats[player_id]
        self.sitting_out.discard(player_id)
        self.round.drop(player_id)
        self._auto_reveal()

    def is_seated(self, player_id: str | None) -> bool:
        return player_id is not None and player_id in self.seats

    # Round

    def vote(self, player_id: str, card: str) -> None:
        seat = self._require_seat(player_id)
        if seat.sitting_out:
            raise CommandError("sitting_out", "Join the table to vote.")
        self._require_ticket()
        self.round.vote(player_id, card)
        seat.on_break = False
        self._auto_reveal()

    def take_break(self, player_id: str, on: Any) -> None:
        """Ask for a coffee break, or end one. Other screens see it at once; it is not a
        vote, so the voted count and auto-reveal still wait for the player."""
        if not isinstance(on, bool):
            raise CommandError("invalid_value", "A break is on or off.")
        seat = self._require_seat(player_id)
        if seat.sitting_out:
            raise CommandError("sitting_out", "Join the table to take a break.")
        seat.on_break = on

    def withdraw(self, player_id: str) -> None:
        self._require_seat(player_id)
        self.round.withdraw(player_id)

    def reveal(self) -> None:
        self._require_ticket()
        self.round.reveal()
        if self.countdown_deadline is not None:  # a running countdown stops; time's up stays
            self._clear_countdown()

    def restart(self) -> None:
        self._new_round()

    def points_for(self, value: Any) -> float:
        """Check that the round can be confirmed with this value, and return the points.

        The value is a number, or a card label whose mapped value is used.
        """
        self._require_ticket()
        if self.round.state != REVEALED:
            raise CommandError("not_revealed", "Reveal the cards before confirming points.")
        if isinstance(value, str):
            card = self.round.scale.card(value)
            if card is None or card.value is None:
                raise CommandError("invalid_value", "That card has no numeric value.")
            return card.value
        points = parse_value(value)
        if points is None:
            raise CommandError("invalid_value", "Choose the points to confirm.")
        return points

    def record_estimate(self, points: float) -> None:
        """Mark the round confirmed and move on. Call only once Jira has accepted the write."""
        self.round.confirm()
        self.queue.estimate(points, *self._how_it_went())
        self._new_round()

    def confirm(self, value: Any) -> float:
        """points_for and record_estimate in one step, for callers with nothing to write."""
        points = self.points_for(value)
        self.record_estimate(points)
        return points

    def skip(self) -> None:
        self.queue.skip(*self._how_it_went())
        self._new_round()

    def jump(self, key: Any) -> None:
        """Move straight to a ticket in the queue, leaving the current one as it is."""
        if not isinstance(key, str):
            raise CommandError("unknown_ticket", "That ticket is not in the queue.")
        self.queue.jump(key)
        self._new_round()

    def rewind(self) -> None:
        if self.queue.rewind():
            self._new_round()

    # Settings

    def set_scale(self, scale: Scale) -> None:
        """Change the cards. They apply now if nobody has voted, otherwise from the next round."""
        self.scale = scale
        if self.round.state == VOTING and not self.round.votes:
            self.round = Round(scale)
            self.next_scale = None
        else:
            self.next_scale = scale

    def set_timer(self, seconds: Any) -> None:
        self.timer_seconds = _seconds(seconds)

    def set_sound(self, on: Any) -> None:
        if not isinstance(on, bool):
            raise CommandError("invalid_value", "Sound is on or off.")
        self.sound = on

    def set_auto_reveal(self, on: Any) -> None:
        if not isinstance(on, bool):
            raise CommandError("invalid_value", "Auto-reveal is on or off.")
        self.auto_reveal = on
        self._auto_reveal()

    # Countdown

    def start_countdown(self, seconds: Any = None) -> None:
        duration = self.timer_seconds if seconds is None else _seconds(seconds)
        self.countdown_duration = duration
        self.countdown_deadline = self.clock.now() + duration
        self.time_up = False

    def stop_countdown(self) -> None:
        self._clear_countdown()

    def tick(self) -> bool:
        """Apply any deadline that has passed. Returns True if the state changed."""
        now = self.clock.now()
        changed = False
        if self.countdown_deadline is not None and now >= self.countdown_deadline:
            self.countdown_deadline = None
            self.time_up = True  # signals only; the facilitator decides when to reveal
            changed = True
        if self.check_in_deadline is not None and now >= self.check_in_deadline:
            self.check_in_deadline = None
            changed = True
        return changed

    def next_deadline(self) -> float | None:
        deadlines = [d for d in (self.countdown_deadline, self.check_in_deadline) if d is not None]
        return min(deadlines, default=None)

    # Reset

    def reset(self) -> None:
        """Empty the seats and the cards, then open a short check-in window.

        Settings, the queue position and the session counters stay.
        """
        self.seats.clear()
        self._new_round()
        self.check_in_deadline = self.clock.now() + self.check_in_seconds

    @property
    def check_in_open(self) -> bool:
        return self.check_in_deadline is not None and self.clock.now() < self.check_in_deadline

    def check_in(self, player_id: str, name: str) -> Seat:
        if not self.check_in_open:
            raise CommandError("check_in_closed", "Check-in has closed. Join the room again.")
        return self.join(player_id, name)

    def summary(self) -> list[dict[str, Any]]:
        """This session's estimated and skipped tickets, for facilitators. No names."""
        return self.queue.summary()

    # Snapshot

    def snapshot_for(self, player_id: str | None) -> dict[str, Any]:
        """The state one client may see. Before reveal it holds no other player's card."""
        revealed = self.round.state != VOTING
        players = []
        watchers = []
        for seat in self.seats.values():
            if seat.sitting_out:
                watchers.append(
                    {"id": seat.player_id, "name": seat.name, "connected": seat.connected}
                )
                continue
            entry: dict[str, Any] = {
                "id": seat.player_id,
                "name": seat.name,
                "connected": seat.connected,
                "voted": seat.player_id in self.round.votes,
                "on_break": seat.on_break,
            }
            if revealed:
                card = self.round.votes.get(seat.player_id)
                entry["card"] = None if card is None else card.label
            players.append(entry)

        own = self.round.votes.get(player_id) if player_id is not None else None
        round_: dict[str, Any] = {"state": self.round.state}
        if revealed and self.round.results is not None:
            round_["results"] = self.round.results.to_dict()

        ticket = self.queue.current
        session = self.queue.session()
        seated = self.is_seated(player_id)
        return {
            "type": "state",
            "you": {
                "player_id": player_id,
                "seated": seated,
                "name": self.seats[player_id].name if seated else None,
                "vote": None if own is None else own.label,
                "sitting_out": seated and self.seats[player_id].sitting_out,
                "on_break": seated and self.seats[player_id].on_break,
                "removed": not seated and player_id in self.removed,
            },
            "scale": self.round.scale.to_dict(),
            "next_scale": None if self.next_scale is None else self.next_scale.to_dict(),
            "round": round_,
            "players": players,
            "watchers": watchers,
            "ticket": None
            if ticket is None
            else {
                **ticket.to_dict(),
                "result": self.queue.current_result().to_dict(),
                # Jira's own estimate, for a re-estimate: only once the cards are shown.
                **(
                    {"estimate": number(ticket.story_points)}
                    if ticket.story_points is not None and self.round.state != VOTING
                    else {}
                ),
            },
            "up_next": [{"key": t.key, "summary": t.summary} for t in self.queue.upcoming(UP_NEXT)],
            "queue": {
                "position": min(self.queue.cursor + 1, len(self.queue.tickets)),
                "length": len(self.queue.tickets),
                "finished": self.queue.finished,
            },
            "counters": {
                "session": {"tickets": session.tickets, "points": number(session.points)},
                "backlog": self.queue.backlog_counters(),
            },
            "countdown": self._countdown(),
            "timer_seconds": number(self.timer_seconds),
            "sound": self.sound,
            "auto_reveal": self.auto_reveal,
            "check_in_open": self.check_in_open,
        }

    # Internals

    def _countdown(self) -> dict[str, Any]:
        running = self.countdown_deadline is not None
        remaining = None
        if running:
            remaining = round(max(0.0, self.countdown_deadline - self.clock.now()), 3)
        elif self.time_up:
            remaining = 0
        return {
            "running": running,
            "duration": number(self.countdown_duration),
            "remaining": number(remaining),
            "time_up": self.time_up,
        }

    def _new_round(self) -> None:
        self.next_scale = None
        self.round = Round(self.scale)
        self._clear_countdown()

    def _clear_countdown(self) -> None:
        self.countdown_duration = None
        self.countdown_deadline = None
        self.time_up = False

    def _auto_reveal(self) -> None:
        """With auto-reveal on, reveal once every connected player at the table has voted."""
        if not self.auto_reveal or self.round.state != VOTING or self.queue.current is None:
            return
        at_table = [s for s in self.seats.values() if s.connected and not s.sitting_out]
        if at_table and all(s.player_id in self.round.votes for s in at_table):
            self.reveal()

    def _how_it_went(self) -> tuple[float | None, tuple[tuple[str, int], ...]]:
        """The revealed round's average and spread, for the summary; nothing if unrevealed."""
        results = self.round.results
        if results is None:
            return None, ()
        return results.average, results.spread

    def _require_seat(self, player_id: str) -> Seat:
        if not self.is_seated(player_id):
            raise CommandError("not_seated", "Join the room before voting.")
        return self.seats[player_id]

    def _require_ticket(self) -> None:
        if self.queue.current is None:
            raise CommandError("queue_finished", "There are no more tickets in the queue.")


def _identity(player_id: Any, name: Any) -> tuple[str, str]:
    if not isinstance(player_id, str) or not 0 < len(player_id) <= MAX_PLAYER_ID:
        raise CommandError("invalid_player", "A player ID is required.")
    if not isinstance(name, str) or not 0 < len(name.strip()) <= MAX_NAME:
        raise CommandError("invalid_name", f"A name is 1 to {MAX_NAME} characters.")
    return player_id, name.strip()


def _same_name(a: str, b: str) -> bool:
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def _seconds(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise CommandError("invalid_timer", "The timer is a number of seconds.")
    if not 1 <= value <= MAX_TIMER:
        raise CommandError("invalid_timer", f"The timer runs 1 to {MAX_TIMER} seconds.")
    return float(value)
