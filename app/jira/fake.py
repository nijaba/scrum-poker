"""An in-memory stand-in for Jira, for room-engine tests that do not need HTTP.

It serves one backlog to every room and records point writes. It can be told to
fail, so tests can check that a room stays on its ticket until a write is accepted.
The HTTP-level fake, with OAuth and the Jira endpoints, is app.jira.fake_atlassian.
"""

from __future__ import annotations

import copy
import html
from typing import Any

from app.room.ports import PointsWriteError


class FakeJira:
    def __init__(self, backlog: list[dict[str, Any]] | None = None) -> None:
        self.backlog = copy.deepcopy(backlog or [])
        for ticket in self.backlog:  # descriptions reach the room as HTML, as from Jira
            ticket["description"] = f"<p>{html.escape(ticket.get('description') or '')}</p>"
        self.writes: list[tuple[str, float]] = []
        self.fail_with: str | None = None

    async def load_backlog(self, slug: str) -> list[dict[str, Any]]:
        return copy.deepcopy(self.backlog)

    async def write_points(self, slug: str, ticket_key: str, points: float) -> None:
        if self.fail_with:
            raise PointsWriteError(self.fail_with)
        self.writes.append((ticket_key, points))
        for ticket in self.backlog:
            if ticket["key"] == ticket_key:
                ticket["story_points"] = points
