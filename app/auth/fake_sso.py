"""A local stand-in for Google and GitHub sign-in, for tests, E2E runs and development.

It is mounted at /_fake-sso only when SCRUM_POKER_FAKE_SSO=1, and configuration
refuses that outside localhost. It speaks just enough OAuth 2.0 for the app:
an authorize page, a token endpoint with PKCE, user info and GitHub org membership.
"""

from __future__ import annotations

import base64
import hashlib
import html
import secrets
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

GOOGLE = {
    "owner": {
        "sub": "g-owner",
        "email": "owner@example.com",
        "email_verified": True,
        "name": "Olive Owner",
        "hd": "example.com",
    },
    "delegate": {
        "sub": "g-delegate",
        "email": "delegate@example.com",
        "email_verified": True,
        "name": "Dee Delegate",
    },
    "outsider": {
        "sub": "g-outsider",
        "email": "outsider@example.org",
        "email_verified": True,
        "name": "Otto Outsider",
    },
    "colleague": {
        "sub": "g-colleague",
        "email": "colleague@example.com",
        "email_verified": True,
        "name": "Cole Colleague",
        "hd": "example.com",
    },
    "personal": {
        "sub": "g-personal",
        "email": "pat@example.com",
        "email_verified": True,
        "name": "Pat Personal",
    },
    "unverified": {
        "sub": "g-unverified",
        "email": "owner@example.com",
        "email_verified": False,
        "name": "Una Unverified",
    },
}

GITHUB = {
    "owner": {"id": 1001, "login": "octo-owner", "name": "Octo Owner", "orgs": ["acme"]},
    "delegate": {"id": 1002, "login": "octo-delegate", "name": "Octo Delegate", "orgs": []},
    "outsider": {"id": 1003, "login": "octo-outsider", "name": "Octo Outsider", "orgs": []},
    "member": {"id": 1004, "login": "acme-member", "name": "Acme Member", "orgs": ["acme"]},
}

ACCOUNTS = {"google": GOOGLE, "github": GITHUB}


def fake_sso_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    codes: dict[str, dict[str, Any]] = {}
    tokens: dict[str, tuple[str, str]] = {}

    @app.get("/{provider}/authorize")
    async def authorize(provider: str, request: Request, account: str | None = None):
        accounts = _accounts(provider)
        query = dict(request.query_params)
        redirect_uri, state = query.get("redirect_uri"), query.get("state")
        if not redirect_uri or not state or query.get("code_challenge_method") != "S256":
            raise HTTPException(400, "redirect_uri, state and an S256 code_challenge are required")
        if account is None:
            return HTMLResponse(_chooser(provider, accounts, query))
        if account not in accounts:
            raise HTTPException(400, "unknown account")
        code = secrets.token_urlsafe(16)
        codes[code] = {
            "account": account,
            "provider": provider,
            "redirect_uri": redirect_uri,
            "challenge": query.get("code_challenge"),
        }
        sep = "&" if "?" in redirect_uri else "?"
        return RedirectResponse(
            f"{redirect_uri}{sep}{urlencode({'code': code, 'state': state})}", 302
        )

    @app.post("/{provider}/token")
    async def token(provider: str, request: Request):
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        grant = codes.pop(form.get("code", ""), None)
        if (
            form.get("grant_type") != "authorization_code"
            or grant is None
            or grant["provider"] != provider
            or grant["redirect_uri"] != form.get("redirect_uri")
            or _challenge(form.get("code_verifier", "")) != grant["challenge"]
        ):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        access = secrets.token_urlsafe(16)
        tokens[access] = (provider, grant["account"])
        return {"access_token": access, "token_type": "bearer", "expires_in": 3600}

    def account_for(provider: str, authorization: str | None) -> dict[str, Any]:
        found = tokens.get((authorization or "").removeprefix("Bearer ").strip())
        if found is None or found[0] != provider:
            raise HTTPException(401, "bad token")
        return ACCOUNTS[provider][found[1]]

    @app.get("/google/userinfo")
    async def google_userinfo(authorization: str | None = Header(None)):
        return account_for("google", authorization)

    @app.get("/github/api/user")
    async def github_user(authorization: str | None = Header(None)):
        info = account_for("github", authorization)
        return {k: v for k, v in info.items() if k != "orgs"}

    @app.get("/github/api/user/memberships/orgs/{org}")
    async def github_membership(org: str, authorization: str | None = Header(None)):
        info = account_for("github", authorization)
        if org.lower() not in info["orgs"]:
            raise HTTPException(404, "Not Found")
        return {"state": "active", "role": "member", "organization": {"login": org}}

    return app


def _accounts(provider: str) -> dict[str, dict[str, Any]]:
    if provider not in ACCOUNTS:
        raise HTTPException(404, "unknown provider")
    return ACCOUNTS[provider]


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _chooser(provider: str, accounts: dict[str, dict[str, Any]], query: dict[str, str]) -> str:
    links = []
    for key, info in accounts.items():
        label = info.get("email") or info.get("login")
        href = "?" + urlencode({**query, "account": key})
        links.append(
            f'<li><a href="{html.escape(href)}">{html.escape(info["name"])}</a>'
            f" <small>{html.escape(label)}</small></li>"
        )
    title = "Google" if provider == "google" else "GitHub"
    return (
        "<!doctype html><meta charset=utf-8><title>Fake sign-in</title>"
        "<style>body{font-family:system-ui;margin:48px auto;max-width:28rem;padding:0 16px}"
        "li{margin:12px 0}a{font-size:18px}</style>"
        f"<h1>Fake {title} sign-in</h1><p>For local development and tests only.</p>"
        f"<ul>{''.join(links)}</ul>"
    )
