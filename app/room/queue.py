"""The ticket queue: backlog tickets in rank order, a cursor and per-ticket results.

By default the queue holds the tickets with no estimate; with `include_estimated`
it holds every ticket, for a re-estimation session. Counters are derived from the
results every time they are read, so a rewind and re-estimate replaces the earlier
result and never double counts. A reload carries the session's results over, in
`earlier` for tickets no longer in the queue.
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
    include_estimated: bool = False
    # Results from before a reload: (ticket, result) by key, for tickets that have one.
    earlier: dict[str, tuple[Ticket, TicketResult]] = field(default_factory=dict)
    tickets: list[Ticket] = field(init=False)
    cursor: int = field(init=False, default=0)
    results: dict[str, TicketResult] = field(init=False)

    def __post_init__(self) -> None:
        if self.include_estimated:
            self.tickets = list(self.backlog)
        else:
            self.tickets = [t for t in self.backlog if t.story_points is None]
        carried = self.earlier
        self.results = {
            t.key: carried[t.key][1] if t.key in carried else TicketResult() for t in self.tickets
        }
        self.earlier = {k: v for k, v in carried.items() if k not in self.results}
        # Start at the first ticket with no result this session.
        self.cursor = next(
            (i for i, t in enumerate(self.tickets) if self.results[t.key].status == PENDING),
            len(self.tickets),
        )

    @classmethod
    def from_backlog(
        cls,
        backlog: list[dict[str, Any]],
        include_estimated: bool = False,
        earlier: dict[str, tuple[Ticket, TicketResult]] | None = None,
    ) -> Queue:
        """Build from Jira-shaped dicts. Order is kept: Jira returns rank order."""
        return cls([Ticket.from_dict(t) for t in backlog], include_estimated, dict(earlier or {}))

    def kept(self) -> dict[str, tuple[Ticket, TicketResult]]:
        """Every ticket with a result this session, to carry over a reload."""
        found = dict(self.earlier)
        for ticket in self.tickets:
            result = self.results[ticket.key]
            if result.status != PENDING:
                found[ticket.key] = (ticket, result)
        return found

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
        """Every ticket estimated or skipped this session: those from before a reload that
        left the queue first, then the queue's, in queue order."""
        entries = []
        done = [*self.earlier.values(), *((t, self.results[t.key]) for t in self.tickets)]
        for ticket, result in done:
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

    def _all_results(self) -> list[TicketResult]:
        return [r for _, r in self.earlier.values()] + list(self.results.values())

    def _result_for(self, key: str) -> TicketResult | None:
        if key in self.results:
            return self.results[key]
        return self.earlier[key][1] if key in self.earlier else None

    def session(self) -> Counters:
        estimated = [r for r in self._all_results() if r.status == ESTIMATED]
        return Counters(len(estimated), sum(r.points or 0.0 for r in estimated))

    def backlog_counters(self) -> dict[str, Any]:
        """Each backlog ticket counts once, with this session's points if it has them."""
        count, points = 0, 0.0
        for ticket in self.backlog:
            result = self._result_for(ticket.key)
            if result is not None and result.status == ESTIMATED:
                count, points = count + 1, points + (result.points or 0.0)
            elif ticket.story_points is not None:
                count, points = count + 1, points + ticket.story_points
        return {"estimated": count, "total": len(self.backlog), "points": number(points)}

    def _require_current(self) -> Ticket:
        ticket = self.current
        if ticket is None:
            raise CommandError("queue_finished", "There are no more tickets in the queue.")
        return ticket
