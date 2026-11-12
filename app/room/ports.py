"""What the live room needs from the outside world: a clock, a backlog and a points writer.

In the app, app.jira.client.JiraRooms provides the last two through the room's own
Jira connection. Unit and room tests use the in-memory app.jira.fake.FakeJira.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol


class Clock(Protocol):
    def now(self) -> float: ...

    async def sleep_until(self, deadline: float) -> None: ...


class SystemClock:
    def now(self) -> float:
        return time.monotonic()

    async def sleep_until(self, deadline: float) -> None:
        await asyncio.sleep(max(0.0, deadline - self.now()))


class BacklogError(Exception):
    """The backlog could not load. The message is shown in the room; `code` is stable."""

    def __init__(self, message: str, code: str = "backlog_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class BacklogSource(Protocol):
    async def load_backlog(self, slug: str) -> list[dict[str, Any]]:
        """The room's board backlog in Jira's rank order, as ticket dicts. Raise BacklogError."""
        ...


class PointsWriteError(Exception):
    """Jira did not accept a write. The message is shown to facilitators; `code` is stable."""

    def __init__(self, message: str = "", code: str = "write_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class PointsWriter(Protocol):
    async def write_points(self, slug: str, ticket_key: str, points: float) -> None:
        """Write the estimate through the room's Jira connection. Raise PointsWriteError."""
        ...
