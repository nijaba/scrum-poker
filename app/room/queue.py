"""The ticket queue: unestimated backlog tickets in rank order, a cursor and per-ticket results.

Counters are derived from the results every time they are read, so a rewind and
re-estimate replaces the earlier result and never double counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.room.errors import CommandError
from app.room.scales import number

PENDING = "pending"
ESTIMATED = "estimated"
SKIPPED = "skipped"


@dataclass(frozen=True)
class Ticket:
    key: str
    summary: str = ""
    type: str | None = None
    priority: str | None = None
    epic: str | None = None
    labels: tuple[str, ...] = ()
    description: str = ""
    story_points: float | None = None
    rank: int | None = None
    url: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Ticket:
        points = data.get("story_points")
        return Ticket(
            key=data["key"],
            summary=data.get("summary") or "",
            type=data.get("type"),
            priority=data.get("priority"),
            epic=data.get("epic"),
            labels=tuple(data.get("labels") or ()),
            description=data.get("description") or "",
            story_points=None if points is None else float(points),
            rank=data.get("rank"),
            url=data.get("url"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "summary": self.summary,
            "type": self.type,
            "priority": self.priority,
            "epic": self.epic,
            "labels": list(self.labels),
            "description": self.description,
            "url": self.url,
        }


@dataclass(frozen=True)
class TicketResult:
    status: str = PENDING
    points: float | None = None
    # How the vote went, for the session summary: the average on reveal and how many
    # chose each card. Never who chose what.
    average: float | None = None
    votes: tuple[tuple[str, int], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "points": number(self.points)}


@dataclass(frozen=True)
class Counters:
    tickets: int
    points: float


@dataclass
class Queue:
    backlog: list[Ticket]
    tickets: list[Ticket] = field(init=False)
    cursor: int = field(init=False, default=0)
    results: dict[str, TicketResult] = field(init=False)

    def __post_init__(self) -> None:
        self.tickets = [t for t in self.backlog if t.story_points is None]
        self.results = {t.key: TicketResult() for t in self.tickets}

    @classmethod
    def from_backlog(cls, backlog: list[dict[str, Any]]) -> Queue:
        """Build from Jira-shaped dicts. Order is kept: Jira returns rank order."""
        return cls([Ticket.from_dict(t) for t in backlog])

    @property
    def finished(self) -> bool:
        return self.cursor >= len(self.tickets)

    @property
    def current(self) -> Ticket | None:
        return None if self.finished else self.tickets[self.cursor]

    def upcoming(self, count: int) -> list[Ticket]:
        return self.tickets[self.cursor + 1 : self.cursor + 1 + count]

    def current_result(self) -> TicketResult | None:
        ticket = self.current
        return None if ticket is None else self.results[ticket.key]

    def estimate(
        self,
        points: float,
        average: float | None = None,
        votes: tuple[tuple[str, int], ...] = (),
    ) -> None:
        ticket = self._require_current()
        self.results[ticket.key] = TicketResult(ESTIMATED, points, average, votes)
        self.cursor += 1

    def skip(self, average: float | None = None, votes: tuple[tuple[str, int], ...] = ()) -> None:
        ticket = self._require_current()
        if self.results[ticket.key].status == PENDING:
            self.results[ticket.key] = TicketResult(SKIPPED, None, average, votes)
        self.cursor += 1

    def rewind(self) -> bool:
        """Go back one ticket. Returns False on the first ticket, where nothing changes."""
        if self.cursor == 0:
            return False
        self.cursor -= 1
        return True

    def jump(self, key: str) -> None:
        """Move straight to a ticket in the queue. Tickets passed over keep their results."""
        index = next((i for i, t in enumerate(self.tickets) if t.key == key), None)
        if index is None:
            raise CommandError("unknown_ticket", "That ticket is not in the queue.")
        self.cursor = index

    def summary(self) -> list[dict[str, Any]]:
        """Every ticket estimated or skipped this session, in queue order."""
        entries = []
        for ticket in self.tickets:
            result = self.results[ticket.key]
            if result.status == PENDING:
                continue
            entries.append(
                {
                    "key": ticket.key,
                    "summary": ticket.summary,
                    "status": result.status,
                    "points": number(result.points),
                    "average": result.average,
                    "votes": [{"label": label, "count": count} for label, count in result.votes],
                }
            )
        return entries

    def session(self) -> Counters:
        estimated = [r for r in self.results.values() if r.status == ESTIMATED]
        return Counters(len(estimated), sum(r.points or 0.0 for r in estimated))

    def backlog_counters(self) -> dict[str, Any]:
        already = [t for t in self.backlog if t.story_points is not None]
        session = self.session()
        return {
            "estimated": len(already) + session.tickets,
            "total": len(self.backlog),
            "points": number(sum(t.story_points or 0.0 for t in already) + session.points),
        }

    def _require_current(self) -> Ticket:
        ticket = self.current
        if ticket is None:
            raise CommandError("queue_finished", "There are no more tickets in the queue.")
        return ticket
