"""Test doubles shared by room tests."""

from __future__ import annotations

import asyncio
import threading

import httpx2


class FakeClock:
    """A clock that only moves when a test calls `advance`.

    `advance` may be called from the test thread while the room runs on the
    test client's event loop, so sleepers are woken thread-safely.
    """

    def __init__(self, start: float = 1000.0) -> None:
        self._now = start
        self._lock = threading.Lock()
        self._sleepers: list[tuple[float, asyncio.Future, asyncio.AbstractEventLoop]] = []

    def now(self) -> float:
        return self._now

    async def sleep_until(self, deadline: float) -> None:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        entry = (deadline, future, loop)
        with self._lock:
            if deadline <= self._now:
                return
            self._sleepers.append(entry)
        try:
            await future
        finally:
            with self._lock:
                if entry in self._sleepers:
                    self._sleepers.remove(entry)

    def advance(self, seconds: float) -> None:
        with self._lock:
            self._now += seconds
            due = [s for s in self._sleepers if s[0] <= self._now]
        for _, future, loop in due:
            loop.call_soon_threadsafe(_wake, future)


def _wake(future: asyncio.Future) -> None:
    if not future.done():
        future.set_result(None)


class FlakyTransport(httpx2.AsyncBaseTransport):
    """Wraps an httpx2 transport. While `down` is True, every request fails to connect."""

    def __init__(self, inner: httpx2.AsyncBaseTransport) -> None:
        self._inner = inner
        self.down = False

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        if self.down:
            raise httpx2.ConnectError("Jira is unreachable", request=request)
        return await self._inner.handle_async_request(request)
