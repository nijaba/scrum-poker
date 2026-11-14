"""E2E fixtures: a real uvicorn server on the fake backlog, and browsers via Playwright.

These tests need the built front end (`npm run build` in frontend/) and the
Playwright browsers. They skip, with the reason, when either is missing.
Each test gets its own server and room, so tests never see each other's state.
"""

from __future__ import annotations

import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist" / "index.html"
BACKLOG = ROOT / "tests" / "fixtures" / "fake_backlog.json"

if not DIST.is_file():
    pytest.skip("front end not built: run `npm run build` in frontend/", allow_module_level=True)

try:
    from playwright.sync_api import Browser, BrowserContext, Page, expect
except ImportError:  # pragma: no cover
    pytest.skip("playwright is not installed", allow_module_level=True)

expect.set_options(timeout=5_000)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server(str):
    """The app's address, which also knows the SQLite file the server uses."""

    database: Path


@contextmanager
def serve(folder: Path, tls: tuple[Path, Path] | None = None) -> Iterator[str]:
    """Run the app on a free port with the fake sign-in and the fake Jira; yield its address.

    With `tls` (a certificate and key file), uvicorn serves HTTPS itself, as the proxy
    would in production, and the app's address is https://localhost.
    """
    path = folder / "backlog.json"
    path.write_text(BACKLOG.read_text())
    port = _free_port()
    base = Server(f"{'https' if tls else 'http'}://localhost:{port}")
    base.database = folder / "rooms.sqlite3"
    env = {
        **os.environ,
        "SCRUM_POKER_FAKE_BACKLOG": str(path),
        "SCRUM_POKER_FAKE_SSO": "1",
        "SCRUM_POKER_FAKE_JIRA": "1",
        "DEMO_ROOMS": "1",
        "DEMO_IDLE_SECONDS": "2700",  # not the default, so DR-14 sees the setting
        "APP_BASE_URL": base,
        "ROOM_CREATOR_ALLOWLIST": "owner@example.com",
        "DATABASE_PATH": str(base.database),
        "SESSION_SECRET": "e2e-secret-" + "x" * 32,
    }
    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)]
    command += ["--workers", "1"]
    if tls:
        command += ["--ssl-certfile", str(tls[0]), "--ssl-keyfile", str(tls[1])]
        env["SSL_CERT_FILE"] = str(tls[0])  # its calls to its own fakes trust the certificate
    process = subprocess.Popen(
        command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    unverified = ssl._create_unverified_context()  # the test's own throwaway certificate
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"{base}/healthz", timeout=0.5, context=unverified)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("the server did not start")
        yield base
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture
def server(tmp_path_factory) -> Iterator[str]:
    """The app on a free port, with the fake sign-in and the fake Jira serving the fake backlog.

    One server per test: the fake Jira keeps confirmed points, as Jira does, so a
    shared server would let one test's writes change the next test's queue.
    """
    with serve(tmp_path_factory.mktemp("e2e")) as base:
        yield base


@dataclass
class Seat:
    """One person at the table: their browser context and page."""

    name: str
    context: BrowserContext
    page: Page

    def card(self, label: str):
        return self.page.get_by_role("region", name="Your card").get_by_role(
            "button", name="Not sure" if label == "?" else label, exact=True
        )

    def vote(self, label: str) -> None:
        self.card(label).click()
        expect(self.card(label)).to_have_attribute("aria-pressed", "true")

    def press(self, name: str) -> None:
        self.page.get_by_role("button", name=name, exact=True).click()


def sign_in(page: Page, base: str, account: str, next_path: str = "/") -> None:
    """Sign in through the fake provider's account chooser, as a person would."""
    page.goto(f"{base}/auth/google/login?next={next_path}")
    page.get_by_role("link", name=account).click()
    page.wait_for_url(f"{base}{next_path}*")


def connect_jira(page: Page, base: str, slug: str, board: str = "SHOP board") -> None:
    """The owner connects the room to the fake Jira and picks a board, through the settings page."""
    page.goto(f"{base}/r/{slug}/settings")
    page.get_by_role("link", name="Connect Jira").click()
    page.get_by_role("link", name="Accept").click()
    page.wait_for_url(f"{base}/r/{slug}/settings?jira=connected")
    page.get_by_label("Board").select_option(label=board)
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_text("Saved.")).to_be_visible()


class Table:
    """Opens browsers on one fresh room, created by the signed-in owner."""

    def __init__(self, browser: Browser, base: str) -> None:
        self.browser = browser
        self.base = base
        self.database: Path | None = getattr(base, "database", None)
        self.slug = f"e2e-{uuid.uuid4().hex[:8]}"
        self.url = f"{base}/r/{self.slug}"
        self.contexts: list[BrowserContext] = []
        self.owner = self.new_context()
        page = self.owner.new_page()
        sign_in(page, base, "Olive Owner")
        response = self.owner.request.post(f"{base}/api/rooms", data={"slug": self.slug})
        assert response.status == 201, response.text()
        connect_jira(page, base, self.slug)
        page.close()

    def new_context(self) -> BrowserContext:
        context = self.browser.new_context()
        self.contexts.append(context)
        return context

    def open(self, context: BrowserContext) -> Page:
        page = context.new_page()
        page.goto(self.url)
        return page

    def join(self, name: str, facilitator: bool = False) -> Seat:
        """A browser opens the link and types a name, as a first-time player does.

        The facilitator is the owner's signed-in browser; everyone else gets a new one.
        """
        context = self.owner if facilitator else self.new_context()
        page = self.open(context)
        page.get_by_label("Your name").fill(name)
        page.get_by_role("button", name="Join room").click()
        seat = Seat(name, context, page)
        expect(page.get_by_role("region", name="Your card")).to_be_visible()
        return seat

    def close(self) -> None:
        for context in self.contexts:
            context.close()


@pytest.fixture
def table(browser: Browser, server: str) -> Iterator[Table]:
    t = Table(browser, server)
    yield t
    t.close()


def players(page: Page):
    return page.locator("[data-player]")
