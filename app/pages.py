"""Serves the built single-page app: `/`, `/r/<slug>`, `/r/<slug>/settings`, its assets and icons.

A retired room name redirects to the room's current one. An unknown room gets the
page with a 404 status, and the page explains.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.room.ws import SLUG

DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"

# Icons Vite copies from frontend/public to the root of the build.
ICONS = ("favicon.svg", "favicon.ico", "apple-touch-icon.png")
ICON_CACHE = "public, max-age=86400"

NOT_BUILT = """<!doctype html><title>Scrum poker</title>
<p>The front end is not built. Run <code>npm run build</code> in <code>frontend/</code>.</p>
"""


def mount_pages(app: FastAPI, static_dir: Path) -> None:
    index = static_dir / "index.html"
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    router = APIRouter()

    def page(status: int = 200) -> Response:
        if not index.is_file():
            return HTMLResponse(NOT_BUILT, status_code=503)
        return FileResponse(index, status_code=status, headers={"Cache-Control": "no-cache"})

    async def room_page(slug: str, request: Request, suffix: str) -> Response:
        current = None
        if SLUG.match(slug):
            current = await asyncio.to_thread(request.app.state.store.resolve, slug)
        if current is None:
            return page(404)
        if current != slug:
            return RedirectResponse(f"/r/{current}{suffix}", status_code=308)
        return page()

    @router.get("/", include_in_schema=False)
    async def home() -> Response:
        return page()

    @router.get("/r/{slug}", include_in_schema=False)
    async def room(slug: str, request: Request) -> Response:
        return await room_page(slug, request, "")

    @router.get("/r/{slug}/settings", include_in_schema=False)
    async def settings(slug: str, request: Request) -> Response:
        return await room_page(slug, request, "/settings")

    def icon_route(name: str) -> None:
        path = static_dir / name

        @router.get(f"/{name}", include_in_schema=False)
        async def icon() -> Response:
            if not path.is_file():
                return Response(status_code=404)
            return FileResponse(path, headers={"Cache-Control": ICON_CACHE})

    for name in ICONS:
        icon_route(name)

    app.include_router(router)
