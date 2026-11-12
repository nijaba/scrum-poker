"""Google and GitHub sign-in with Authlib's OAuth 2.0 client, and the signed session cookie.

The flow is the authorization-code grant with PKCE. Its state and code verifier
travel in a short-lived signed cookie, so the server keeps no sign-in state.
Owners and delegates sign in; players never do.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import httpx2
from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuthError
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.auth.identity import Identity
from app.config import ProviderConfig, Settings

log = logging.getLogger(__name__)

SESSION_COOKIE = "sp_session"
STATE_COOKIE = "sp_oauth"
SESSION_MAX_AGE = 30 * 24 * 60 * 60
STATE_MAX_AGE = 10 * 60

router = APIRouter()


class SignInError(Exception):
    """The provider's answer cannot sign anyone in. The message is safe to show."""


class Auth:
    """Signs and reads the session cookie, and talks to the providers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sessions = URLSafeTimedSerializer(settings.session_secret, salt="session")
        self._states = URLSafeTimedSerializer(settings.session_secret, salt="oauth-state")
        # Tests point this at the app itself, to reach the fake provider in-process.
        self.transport: httpx2.AsyncBaseTransport | None = None

    def session_value(self, identity: Identity) -> str:
        return self._sessions.dumps(identity.to_dict())

    def identity(self, cookies: Mapping[str, str]) -> Identity | None:
        """The signed-in account, or None. A tampered or expired cookie means signed out."""
        value = cookies.get(SESSION_COOKIE)
        if not value:
            return None
        try:
            data = self._sessions.loads(value, max_age=SESSION_MAX_AGE)
        except BadSignature:
            return None
        return Identity.from_dict(data)

    def can_create(self, identity: Identity | None) -> bool:
        return self.settings.allowlist.allows(identity)

    def client(self, provider: ProviderConfig) -> AsyncOAuth2Client:
        kwargs: dict[str, Any] = {"timeout": 10.0}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            scope=provider.scope,
            redirect_uri=provider.callback_url,
            code_challenge_method="S256",
            **kwargs,
        )

    def set_cookie(self, response: Response, name: str, value: str, max_age: int) -> None:
        response.set_cookie(
            name,
            value,
            max_age=max_age,
            httponly=True,
            samesite="lax",
            secure=self.settings.secure_cookies,
        )


def get_auth(request: Request) -> Auth:
    return request.app.state.auth


def safe_next(target: str | None) -> str:
    """Only paths on this site, so the sign-in cannot be used as an open redirect."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/"
    return target


@router.get("/auth/{provider}/login")
async def login(provider: str, request: Request, next: str = "/") -> Response:
    auth = get_auth(request)
    config = auth.settings.providers.get(provider)
    if config is None:
        raise HTTPException(404, "That sign-in provider is not configured.")
    verifier = generate_token(48)
    async with auth.client(config) as client:
        url, state = client.create_authorization_url(config.authorize_url, code_verifier=verifier)
    response = RedirectResponse(url, status_code=303)
    value = auth._states.dumps({"s": state, "v": verifier, "p": provider, "n": safe_next(next)})
    auth.set_cookie(response, STATE_COOKIE, value, STATE_MAX_AGE)
    return response


@router.get("/auth/{provider}/callback")
async def callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    auth = get_auth(request)
    config = auth.settings.providers.get(provider)
    if config is None:
        raise HTTPException(404, "That sign-in provider is not configured.")
    try:
        saved = auth._states.loads(request.cookies.get(STATE_COOKIE, ""), max_age=STATE_MAX_AGE)
    except BadSignature:
        return _failed("The sign-in took too long or started in another browser. Try again.")
    if saved.get("p") != provider or not state or saved.get("s") != state:
        return _failed("The sign-in could not be checked. Try again.")
    if error or not code:
        response = RedirectResponse("/?signin=denied", status_code=303)
        response.delete_cookie(STATE_COOKIE)
        return response

    try:
        async with auth.client(config) as client:
            await client.fetch_token(config.token_url, code=code, code_verifier=saved["v"])
            identity = await fetch_identity(config, client, auth.settings.allowlist.github_orgs)
    except SignInError as err:
        return _failed(str(err))
    except (OAuthError, httpx2.HTTPError, KeyError, ValueError) as err:
        log.warning("%s sign-in failed: %r", provider, err)
        return _failed("The sign-in provider did not answer as expected. Try again.")

    response = RedirectResponse(saved.get("n") or "/", status_code=303)
    response.delete_cookie(STATE_COOKIE)
    auth.set_cookie(response, SESSION_COOKIE, auth.session_value(identity), SESSION_MAX_AGE)
    return response


@router.post("/auth/logout", status_code=204)
async def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/api/me")
async def me(request: Request) -> dict[str, Any]:
    auth = get_auth(request)
    providers = list(auth.settings.providers)
    identity = auth.identity(request.cookies)
    if identity is None:
        return {"signed_in": False, "providers": providers}
    return {
        "signed_in": True,
        "provider": identity.provider,
        "name": identity.name,
        "label": identity.label,
        "can_create": auth.can_create(identity),
        "providers": providers,
    }


async def fetch_identity(
    config: ProviderConfig, client: AsyncOAuth2Client, github_orgs: tuple[str, ...]
) -> Identity:
    if config.name == "google":
        info = (await client.get(config.userinfo_url)).raise_for_status().json()
        email = info.get("email")
        if not email or info.get("email_verified") is not True:
            raise SignInError("Google did not confirm that this account's email is verified.")
        return Identity(
            provider="google",
            subject=str(info["sub"]),
            name=info.get("name") or email,
            email=email.lower(),
            domain=(info.get("hd") or "").lower() or None,
        )

    headers = {"Accept": "application/vnd.github+json"}
    info = (await client.get(config.userinfo_url, headers=headers)).raise_for_status().json()
    orgs = []
    for org in github_orgs:
        membership = await client.get(
            f"{config.api_url}/user/memberships/orgs/{org}", headers=headers
        )
        if membership.status_code == 200 and membership.json().get("state") == "active":
            orgs.append(org)
    return Identity(
        provider="github",
        subject=str(info["id"]),
        name=info.get("name") or info["login"],
        login=info["login"],
        orgs=tuple(orgs),
    )


def _failed(message: str) -> HTMLResponse:
    body = (
        "<!doctype html><meta charset=utf-8><title>Sign-in failed</title>"
        f"<p>{_escape(message)}</p><p><a href='/'>Back to Scrum poker</a></p>"
    )
    response = HTMLResponse(body, status_code=400)
    response.delete_cookie(STATE_COOKIE)
    return response


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
