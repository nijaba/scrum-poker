"""Shared test fixtures."""

import json
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import FAKE_SSO_PATH, Allowlist, Settings, provider_config
from app.jira.fake import FakeJira
from app.main import create_app
from app.store.rooms import RoomRecord
from tests.fakes import FakeClock
from tests.identities import BASE, OWNER

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_backlog() -> list[dict]:
    """The fake backlog from the test plan, in Jira rank order.

    12 tickets: 8 without an estimate, 4 with estimates totalling 16 points.
    """
    return json.loads((FIXTURES / "fake_backlog.json").read_text())


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def jira(fake_backlog) -> FakeJira:
    return FakeJira(fake_backlog)


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Localhost, the fake SSO provider, a fresh SQLite file, and an allowlist of the owners."""
    return Settings(
        base_url=BASE,
        session_secret="t" * 40,
        allowlist=Allowlist.parse("owner@example.com,github:octo-owner"),
        database_path=tmp_path / "rooms.sqlite3",
        providers={
            name: provider_config(name, BASE, "fake", "fake", fake_root=BASE + FAKE_SSO_PATH)
            for name in ("google", "github")
        },
        fake_sso=True,
    )


@pytest.fixture
def app(settings, jira, clock, tmp_path):
    """The app on the fake backlog. Its OAuth calls reach the fake provider in-process."""
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Scrum poker</title>")
    app = create_app(
        settings=settings, backlog_source=jira, points_writer=jira, clock=clock, static_dir=static
    )
    app.state.auth.transport = httpx2.ASGITransport(app=app)
    return app


@pytest.fixture
def client(app):
    """HTTP and WebSocket test client, with the room "team-a" owned by OWNER.

    Used as a context manager so every WebSocket shares one event loop, as
    live rooms do in production.
    """
    app.state.store.create(RoomRecord("team-a", OWNER.key, OWNER.label))
    with TestClient(app, base_url=BASE) as client:
        yield client
