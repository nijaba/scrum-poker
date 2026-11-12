"""Checks shared by the JSON endpoints."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app.config import is_local_host


def check_write(request: Request) -> None:
    """Refuse writes from other sites: a foreign Origin, or a body that is not JSON.

    Cookies are SameSite=Lax, and a cross-site page cannot send JSON, PATCH or
    DELETE without a CORS preflight, which this app never grants.
    """
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    if origin is not None and origin != settings.origin:
        if not (settings.is_local and is_local_host(urlsplit(origin).hostname)):
            raise HTTPException(403, "Cross-site request refused.")
    if request.method in ("POST", "PATCH"):
        kind = request.headers.get("content-type", "").split(";")[0].strip()
        if kind != "application/json":
            raise HTTPException(415, "Send JSON.")
