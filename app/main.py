"""Application entry point.

Run with a single worker, because live rooms sit in process memory:

    uvicorn app.main:app --port 8000

Configuration comes from environment variables; see app/config.py and .env.example.
Development-only variables:
    SCRUM_POKER_FAKE_JIRA     1 to use the fake Jira Cloud at /_fake-jira (localhost only)
    SCRUM_POKER_FAKE_BACKLOG  path to a backlog JSON file: the fake Jira's "SHOP board"
    SCRUM_POKER_STATIC_DIR    the built front end; defaults to frontend/dist
    SCRUM_POKER_FAKE_SSO      1 to sign in through the fake provider at /_fake-sso (localhost only)
"""

import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.auth.fake_sso import fake_sso_app
from app.auth.oauth import Auth
from app.auth.oauth import router as auth_router
from app.config import FAKE_JIRA_PATH, FAKE_SSO_PATH, Settings
from app.demo.rooms import DemoRooms
from app.demo.rooms import router as demo_router
from app.https import add_https
from app.jira.client import JiraRooms, JiraService
from app.jira.fake_atlassian import FakeAtlassian
from app.jira.routes import router as jira_router
from app.pages import DEFAULT_STATIC_DIR, mount_pages
from app.players import router as player_router
from app.room.live import RoomRegistry
from app.room.ports import BacklogSource, Clock, PointsWriter, SystemClock
from app.room.ws import router as room_router
from app.rooms_api import router as rooms_router
from app.store.rooms import RoomStore

log = logging.getLogger(__name__)


def create_app(
    *,
    settings: Settings | None = None,
    backlog_source: BacklogSource | None = None,
    points_writer: PointsWriter | None = None,
    clock: Clock | None = None,
    static_dir: Path | None = None,
    fake_atlassian: FakeAtlassian | None = None,
) -> FastAPI:
    """Build the FastAPI application.

    Rooms read their backlog from, and write points to, Jira through their own
    connection. Tests may pass an in-memory backlog source and points writer instead.
    """
    settings = settings or Settings.from_env(os.environ)
    clock = clock or SystemClock()
    store = RoomStore(settings.database_path)
    jira = JiraService(settings, store, clock)
    rooms = RoomRegistry(
        backlog=backlog_source or JiraRooms(jira),
        writer=points_writer or JiraRooms(jira),
        clock=clock,
    )

    demo = None
    if settings.demo_rooms:
        demo = DemoRooms(
            clock,
            max_rooms=settings.demo_max_rooms,
            idle_seconds=settings.demo_idle_seconds,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        if demo is not None:
            await demo.close()
        await rooms.close()
        store.close()

    app = FastAPI(title="Scrum poker", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.rooms = rooms
    app.state.demo = demo
    app.state.auth = Auth(settings)
    app.state.jira = jira
    app.include_router(room_router)
    app.include_router(player_router)
    app.include_router(jira_router)  # before auth: /auth/atlassian/* is not a sign-in provider
    app.include_router(auth_router)
    app.include_router(rooms_router)
    app.include_router(demo_router)

    if settings.fake_sso:
        log.warning(
            "Sign-in uses the FAKE SSO provider at %s. Never use this in production.", FAKE_SSO_PATH
        )
        app.mount(FAKE_SSO_PATH, fake_sso_app())
    if settings.fake_jira:
        log.warning(
            "Jira is the FAKE Jira Cloud at %s. Never use this in production.", FAKE_JIRA_PATH
        )
        fake = fake_atlassian or FakeAtlassian(_fake_backlog_from_env())
        app.state.fake_atlassian = fake
        app.mount(FAKE_JIRA_PATH, fake.app)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    if not settings.is_local:
        add_https(app, settings.base_url, settings.forwarded_allow_ips)

    static = static_dir or Path(os.environ.get("SCRUM_POKER_STATIC_DIR", DEFAULT_STATIC_DIR))
    mount_pages(app, static)
    return app


def _fake_backlog_from_env() -> list[dict]:
    path = os.environ.get("SCRUM_POKER_FAKE_BACKLOG")
    return json.loads(Path(path).read_text()) if path else []


app = create_app()
