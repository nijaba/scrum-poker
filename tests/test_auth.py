"""Sign-in with Google and GitHub through the fake SSO provider, at Integration level.

Cases AR-01, AR-02, AR-04, AR-05, HS-04, HS-05 (Google and GitHub).
"""

from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import FAKE_SSO_PATH, Allowlist, Settings, provider_config
from app.main import create_app
from tests.identities import BASE

SESSION = "sp_session"


def sign_in(client, provider, account, next_path="/"):
    """Walk the visitor through the OAuth redirects. Returns the final callback response."""
    start = client.get(
        f"/auth/{provider}/login", params={"next": next_path}, follow_redirects=False
    )
    assert start.status_code == 303, start.text
    authorize = start.headers["location"]
    approved = client.get(f"{authorize}&account={account}", follow_redirects=False)
    assert approved.status_code == 302, approved.text
    return client.get(approved.headers["location"], follow_redirects=False)


def me(client):
    return client.get("/api/me").json()


def create_room(client, slug):
    return client.post(
        "/api/rooms", json={"slug": slug}, headers={"origin": client.base_url_origin}
    )


@pytest.fixture
def visitor(app):
    """A fresh visitor on the app, with its own cookies."""
    c = TestClient(app, base_url=BASE)
    c.base_url_origin = BASE
    return c


def test_ar01_owner_signs_in_with_google(visitor):
    done = sign_in(visitor, "google", "owner", next_path="/r/whatever")

    assert done.status_code == 303
    assert done.headers["location"] == "/r/whatever"
    cookie = done.headers["set-cookie"]
    assert f"{SESSION}=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    assert "owner@example.com" not in visitor.cookies[SESSION]  # signed, not plain text
    assert me(visitor) == {
        "signed_in": True,
        "provider": "google",
        "name": "Olive Owner",
        "label": "owner@example.com",
        "can_create": True,
        "providers": ["google", "github"],
    }
    assert create_room(visitor, "team-g").status_code == 201


def test_ar02_owner_signs_in_with_github(visitor):
    done = sign_in(visitor, "github", "owner")

    assert done.status_code == 303
    info = me(visitor)
    assert (info["provider"], info["label"], info["can_create"]) == ("github", "octo-owner", True)
    assert create_room(visitor, "team-gh").status_code == 201


def test_ar04_account_not_on_the_allowlist_cannot_create_rooms(visitor):
    sign_in(visitor, "google", "outsider")

    assert me(visitor)["signed_in"] is True
    assert me(visitor)["can_create"] is False
    response = create_room(visitor, "nope")
    assert response.status_code == 403
    assert visitor.get("/api/rooms/nope").status_code == 404


def test_signed_out_cannot_create_rooms(visitor):
    assert me(visitor) == {"signed_in": False, "providers": ["google", "github"]}
    assert create_room(visitor, "nope").status_code == 401


def test_ar05_tampered_session_cookie_is_treated_as_signed_out(visitor):
    sign_in(visitor, "google", "owner")
    good = visitor.cookies[SESSION]

    for bad in [good[:-2] + ("AA" if not good.endswith("AA") else "BB"), "e30", "x.y.z"]:
        visitor.cookies.clear()  # replace the real cookie, not add beside it
        visitor.cookies.set(SESSION, bad)
        assert me(visitor)["signed_in"] is False
        assert create_room(visitor, "nope").status_code == 401


def test_session_signed_with_another_secret_is_rejected(app, settings, visitor):
    other = create_app(settings=Settings(**{**settings.__dict__, "session_secret": "o" * 40}))
    from tests.identities import OWNER

    visitor.cookies.set(SESSION, other.state.auth.session_value(OWNER))
    assert me(visitor)["signed_in"] is False


def test_sign_out(visitor):
    sign_in(visitor, "google", "owner")
    assert visitor.post("/auth/logout", headers={"origin": BASE}).status_code == 204
    assert me(visitor)["signed_in"] is False


def test_unverified_google_email_is_refused(visitor):
    done = sign_in(visitor, "google", "unverified")

    assert done.status_code == 400
    assert me(visitor)["signed_in"] is False


def test_state_must_match(visitor):
    start = visitor.get("/auth/google/login", follow_redirects=False)
    approved = visitor.get(start.headers["location"] + "&account=owner", follow_redirects=False)
    callback = urlsplit(approved.headers["location"])
    query = parse_qs(callback.query)

    forged = visitor.get(
        "/auth/google/callback",
        params={"code": query["code"][0], "state": "forged"},
        follow_redirects=False,
    )
    assert forged.status_code == 400
    assert me(visitor)["signed_in"] is False


def test_callback_without_the_state_cookie_is_refused(app, visitor):
    start = visitor.get("/auth/google/login", follow_redirects=False)
    approved = visitor.get(start.headers["location"] + "&account=owner", follow_redirects=False)

    other = TestClient(app, base_url=BASE)  # a different visitor, without the state cookie
    assert other.get(approved.headers["location"], follow_redirects=False).status_code == 400


def test_denied_consent_returns_home(visitor):
    start = visitor.get("/auth/github/login", follow_redirects=False)
    query = parse_qs(urlsplit(start.headers["location"]).query)
    done = visitor.get(
        "/auth/github/callback",
        params={"error": "access_denied", "state": query["state"][0]},
        follow_redirects=False,
    )
    assert done.status_code == 303
    assert done.headers["location"] == "/?signin=denied"


@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example/", "javascript:x"])
def test_next_must_stay_on_this_site(visitor, target):
    assert sign_in(visitor, "google", "owner", next_path=target).headers["location"] == "/"


def test_unknown_provider(visitor):
    assert visitor.get("/auth/slack/login", follow_redirects=False).status_code == 404


# Allowlist variants


def _browser_with(settings, jira, clock, allowlist):
    app = create_app(
        settings=Settings(**{**settings.__dict__, "allowlist": Allowlist.parse(allowlist)}),
        backlog_source=jira,
        points_writer=jira,
        clock=clock,
    )
    app.state.auth.transport = httpx2.ASGITransport(app=app)
    return TestClient(app, base_url=BASE)


def test_star_lets_anyone_signed_in_create_rooms(settings, jira, clock):
    visitor = _browser_with(settings, jira, clock, "*")
    sign_in(visitor, "github", "outsider")
    assert me(visitor)["can_create"] is True


def test_google_workspace_domain(settings, jira, clock):
    visitor = _browser_with(settings, jira, clock, "google-domain:example.com")
    sign_in(visitor, "google", "colleague")
    assert me(visitor)["can_create"] is True

    other = _browser_with(settings, jira, clock, "google-domain:example.com")
    sign_in(other, "google", "personal")  # an example.com address without the Workspace claim
    assert me(other)["can_create"] is False


def test_github_org_membership(settings, jira, clock):
    org_settings = Settings(
        **{
            **settings.__dict__,
            "providers": {
                "github": provider_config(
                    "github", BASE, "fake", "fake", github_orgs=True, fake_root=BASE + FAKE_SSO_PATH
                )
            },
        }
    )
    visitor = _browser_with(org_settings, jira, clock, "github-org:acme")
    start = visitor.get("/auth/github/login", follow_redirects=False)
    assert "read%3Aorg" in start.headers["location"] or "read:org" in start.headers["location"]

    sign_in(visitor, "github", "member")
    assert me(visitor)["can_create"] is True

    other = _browser_with(org_settings, jira, clock, "github-org:acme")
    sign_in(other, "github", "outsider")
    assert me(other)["can_create"] is False


# HTTPS


def _https_app(settings, jira, clock, fake=True):
    base = "https://poker.example.com"
    providers = {
        name: provider_config(
            name, base, "cid", "secret", fake_root=base + FAKE_SSO_PATH if fake else None
        )
        for name in ("google", "github")
    }
    app = create_app(
        settings=Settings(**{**settings.__dict__, "base_url": base, "providers": providers}),
        backlog_source=jira,
        points_writer=jira,
        clock=clock,
    )
    app.state.auth.transport = httpx2.ASGITransport(app=app)
    return app, base


@pytest.mark.parametrize("provider", ["google", "github"])
def test_hs05_sign_in_returns_to_an_https_callback(settings, jira, clock, provider):
    app, base = _https_app(settings, jira, clock, fake=False)  # the real providers' addresses
    visitor = TestClient(app, base_url=base)

    start = visitor.get(f"/auth/{provider}/login", follow_redirects=False)

    location = urlsplit(start.headers["location"])
    assert location.scheme == "https"
    assert location.netloc in ("accounts.google.com", "github.com")
    query = parse_qs(location.query)
    assert query["redirect_uri"] == [f"https://poker.example.com/auth/{provider}/callback"]
    assert query["code_challenge_method"] == ["S256"]


def test_hs04_session_and_player_cookies_are_secure_outside_localhost(settings, jira, clock):
    app, base = _https_app(settings, jira, clock)
    visitor = TestClient(app, base_url=base)

    done = sign_in(visitor, "google", "owner")
    assert "Secure" in done.headers["set-cookie"]
    player = visitor.post("/api/player", json={"name": "Ana"}, headers={"origin": base})
    assert "Secure" in player.headers["set-cookie"]


def test_cookies_are_not_secure_on_localhost(visitor):
    done = sign_in(visitor, "google", "owner")
    assert "Secure" not in done.headers["set-cookie"]
