"""Jira Cloud through the fake Atlassian, at Integration level.

Cases JC-03, JC-04, JC-07, JC-08, JC-09, JC-10, JC-12, JC-13 and HS-05 (Atlassian).
Each room has one Jira connection, set up by its owner.
"""

import sqlite3
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import FAKE_JIRA_PATH, Settings, atlassian_config
from app.jira.fake_atlassian import ACCOUNT, CLOUD_ID, SITE, FakeAtlassian
from app.jira.html import clean
from app.main import create_app
from app.store.rooms import RoomRecord
from tests.fakes import FlakyTransport
from tests.identities import BASE, DELEGATE, OWNER, headers, open_ws

ROOM = "/ws/rooms/team-a"


@pytest.fixture
def atlassian(fake_backlog, clock):
    return FakeAtlassian(fake_backlog, clock=clock.now)


@pytest.fixture
def jira_settings(settings):
    return Settings(
        **{
            **settings.__dict__,
            "atlassian": atlassian_config(BASE, "fake", "fake", BASE + FAKE_JIRA_PATH),
            "fake_jira": True,
        }
    )


@pytest.fixture
def japp(jira_settings, atlassian, clock, tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Scrum poker</title>")
    app = create_app(
        settings=jira_settings, clock=clock, fake_atlassian=atlassian, static_dir=static
    )
    app.state.auth.transport = httpx2.ASGITransport(app=app)
    app.state.jira.transport = FlakyTransport(httpx2.ASGITransport(app=app))
    app.state.store.create(RoomRecord("team-a", OWNER.key, OWNER.label))
    return app


@pytest.fixture
def jclient(japp):
    with TestClient(japp, base_url=BASE) as client:
        yield client


def connect(app, atlassian, slug="team-a", board_id=1):
    """Seed the room's connection as if the owner had connected Jira and picked a board."""
    store = app.state.store
    token = atlassian.issue_refresh_token()
    store.set_jira_connection(slug, app.state.jira.cipher.seal(token), ACCOUNT["email"])
    store.set_jira_board(slug, CLOUD_ID, SITE["url"], SITE["name"], board_id, "board")


def state(ws, predicate=lambda s: True):
    while True:
        msg = ws.receive_json()
        if msg["type"] == "state" and predicate(msg):
            return msg


def until_type(ws, kind):
    while True:
        msg = ws.receive_json()
        if msg["type"] == kind:
            return msg


def ready(ws):
    return state(ws, lambda s: s["backlog"]["state"] == "ready")


def reveal_and_confirm(ws, card="5"):
    ws.send_json({"type": "vote", "card": card})
    ws.send_json({"type": "reveal"})
    state(ws, lambda s: s["round"]["state"] == "revealed")
    ws.send_json({"type": "confirm", "points": card})


def facilitator(client):
    return open_ws(client, ROOM, OWNER, ("p-own", "Olive"))


# Loading the backlog


def test_jc03_only_unestimated_tickets_enter_the_queue(jclient, japp, atlassian):
    connect(japp, atlassian)

    with facilitator(jclient) as ws:
        snap = ready(ws)

    assert snap["queue"]["length"] == 8
    assert snap["ticket"]["key"] == "SHOP-134"
    assert snap["counters"]["backlog"] == {"estimated": 4, "total": 12, "points": 16}
    assert snap["ticket"]["url"] == "https://shop.atlassian.net/browse/SHOP-134"
    assert snap["ticket"]["epic"] == "Checkout revamp"
    assert snap["ticket"]["description"].startswith("<p>As a shopper")


def test_jc04_a_backlog_of_120_tickets_loads_whole_in_rank_order(jclient, japp, atlassian):
    connect(japp, atlassian, board_id=2)

    with facilitator(jclient) as ws:
        snap = ready(ws)
    tickets = jclient.portal.call(japp.state.jira.backlog, "team-a")

    assert snap["queue"]["length"] == 120
    assert [t["key"] for t in tickets] == [f"BIG-{i}" for i in range(1, 121)]


def test_room_without_a_connection_says_the_owner_must_connect(jclient):
    with facilitator(jclient) as ws:
        snap = state(ws, lambda s: s["backlog"]["state"] == "error")

    assert snap["backlog"]["code"] == "jira_not_connected"
    assert "owner" in snap["backlog"]["message"]
    assert snap["ticket"] is None


def test_room_without_a_board_says_so_and_loads_once_the_owner_picks_one(jclient, japp, atlassian):
    connect(japp, atlassian)
    japp.state.store._set("team-a", jira_board_id=None, jira_cloud_id=None)

    with facilitator(jclient) as ws:
        snap = state(ws, lambda s: s["backlog"]["state"] == "error")
        assert snap["backlog"]["code"] == "jira_no_board"

        response = jclient.put(
            "/api/rooms/team-a/jira/board",
            json={"cloud_id": CLOUD_ID, "board_id": 1},
            headers=headers(japp, OWNER),
        )
        assert response.status_code == 200, response.text
        snap = ready(ws)
        assert snap["ticket"]["key"] == "SHOP-134"


# Writing points


def test_confirm_writes_through_the_estimation_endpoint(jclient, japp, atlassian):
    connect(japp, atlassian)
    with facilitator(jclient) as ws:
        ready(ws)
        reveal_and_confirm(ws, "8")
        snap = state(ws, lambda s: s["ticket"]["key"] == "SHOP-138")

    assert atlassian.writes == [("SHOP-134", "8", 1)]
    assert atlassian.estimate(1, "SHOP-134") == 8
    assert snap["counters"]["session"] == {"tickets": 1, "points": 8}


def test_jc07_rejected_write_shows_the_error_and_stays_on_the_ticket(jclient, japp, atlassian):
    connect(japp, atlassian)
    atlassian.fail_writes = "Field 'Story Points' cannot be set."
    with facilitator(jclient) as ws:
        ready(ws)
        reveal_and_confirm(ws)
        error = until_type(ws, "error")
        ws.send_json({"type": "stop_countdown"})
        snap = state(ws)

    assert error["code"] == "jira_rejected"
    assert "cannot be set" in error["message"]
    assert snap["ticket"]["key"] == "SHOP-134"
    assert snap["round"]["state"] == "revealed"
    assert atlassian.writes == []


def test_jc08_unreachable_jira_keeps_the_ticket_and_a_retry_succeeds(jclient, japp, atlassian):
    connect(japp, atlassian)
    with facilitator(jclient) as ws:
        ready(ws)
        japp.state.jira.transport.down = True
        reveal_and_confirm(ws)
        error = until_type(ws, "error")
        assert error["code"] == "jira_unreachable"

        japp.state.jira.transport.down = False
        ws.send_json({"type": "confirm", "points": "5"})
        snap = state(ws, lambda s: s["ticket"]["key"] == "SHOP-138")

    assert error["message"] == "Could not reach Jira. Try again."
    assert snap["counters"]["session"] == {"tickets": 1, "points": 5}
    assert atlassian.writes == [("SHOP-134", "5", 1)]


def test_jc09_expired_access_token_is_refreshed_and_the_new_refresh_token_stored(
    jclient, japp, atlassian
):
    connect(japp, atlassian)
    store, cipher = japp.state.store, japp.state.jira.cipher
    with facilitator(jclient) as ws:
        ready(ws)
        before = store.get("team-a").jira.token
        refreshes = atlassian.refreshes

        atlassian.expire_access_tokens()
        reveal_and_confirm(ws)
        state(ws, lambda s: s["ticket"]["key"] == "SHOP-138")

    after = store.get("team-a").jira.token
    assert atlassian.refreshes == refreshes + 1
    assert after != before
    assert cipher.open(after) in atlassian.refresh_tokens
    assert cipher.open(before) not in atlassian.refresh_tokens  # rotated away
    assert atlassian.writes == [("SHOP-134", "5", 1)]


def test_access_tokens_are_reused_until_they_expire(jclient, japp, atlassian, clock):
    connect(japp, atlassian)
    with facilitator(jclient) as ws:
        ready(ws)
        refreshes = atlassian.refreshes
        reveal_and_confirm(ws)
        state(ws, lambda s: s["ticket"]["key"] == "SHOP-138")
        assert atlassian.refreshes == refreshes

        clock.advance(3600)  # past the access token's lifetime
        reveal_and_confirm(ws)
        state(ws, lambda s: s["ticket"]["key"] == "SHOP-139")
        assert atlassian.refreshes == refreshes + 1


def test_jc10_invalid_refresh_token_tells_facilitators_the_owner_must_reconnect(
    jclient, japp, atlassian
):
    connect(japp, atlassian)
    jclient.patch(
        "/api/rooms/team-a",
        json={"delegates": [{"provider": "google", "identifier": "delegate@example.com"}]},
        headers=headers(japp, OWNER),
    )
    with facilitator(jclient) as owner, open_ws(jclient, ROOM, DELEGATE) as delegate:
        ready(owner)
        ready(delegate)
        atlassian.expire_access_tokens()
        atlassian.revoke_refresh_tokens()

        reveal_and_confirm(owner)
        mine = until_type(owner, "error")
        theirs = until_type(delegate, "error")
        owner.send_json({"type": "stop_countdown"})
        snap = state(owner)

    assert mine["code"] == theirs["code"] == "jira_reconnect"
    assert "owner" in mine["message"] and "reconnect" in mine["message"]
    assert snap["ticket"]["key"] == "SHOP-134"
    room = jclient.get("/api/rooms/team-a", headers=headers(japp, OWNER)).json()
    assert room["settings"]["jira"]["connected"] is True  # the owner reconnects to fix it


def test_jc12_lapsed_connection_tells_facilitators_and_keeps_the_ticket(jclient, japp, atlassian):
    connect(japp, atlassian)
    with facilitator(jclient) as ws:
        ready(ws)
        disconnected = jclient.delete("/api/rooms/team-a/jira", headers=headers(japp, OWNER))
        assert disconnected.status_code == 204
        reveal_and_confirm(ws)
        error = until_type(ws, "error")
        ws.send_json({"type": "stop_countdown"})
        snap = state(ws)

    assert error["code"] == "jira_not_connected"
    assert error["message"] == "The room's owner needs to connect Jira in the room settings."
    assert snap["ticket"]["key"] == "SHOP-134"


def test_retry_after_the_owner_reconnects(jclient, japp, atlassian):
    with facilitator(jclient) as ws:
        state(ws, lambda s: s["backlog"]["state"] == "error")
        connect(japp, atlassian)
        ws.send_json({"type": "reload_backlog"})
        snap = ready(ws)
        assert snap["ticket"]["key"] == "SHOP-134"


def test_players_cannot_reload_the_backlog(jclient):
    with open_ws(jclient, ROOM, None, ("p1", "Ana")) as ws:
        state(ws)
        ws.send_json({"type": "reload_backlog"})
        assert until_type(ws, "error")["code"] == "forbidden"


# Connecting Jira


def owner_browser(app):
    browser = TestClient(app, base_url=BASE)
    browser.cookies.set("sp_session", app.state.auth.session_value(OWNER))
    return browser


def connect_through_consent(browser, slug="team-a", approve="1"):
    start = browser.get(f"/auth/atlassian/login?room={slug}", follow_redirects=False)
    assert start.status_code == 303, start.text
    consent = browser.get(start.headers["location"] + f"&approve={approve}", follow_redirects=False)
    assert consent.status_code == 302
    return browser.get(consent.headers["location"], follow_redirects=False)


def test_owner_connects_jira_and_picks_a_board(japp, atlassian):
    browser = owner_browser(japp)

    done = connect_through_consent(browser)
    assert done.status_code == 303
    assert done.headers["location"] == "/r/team-a/settings?jira=connected"

    jira = browser.get("/api/rooms/team-a").json()["settings"]["jira"]
    assert jira == {
        "available": True,
        "connected": True,
        "email": "owner@example.com",
        "site": None,
        "board": None,
    }
    sites = browser.get("/api/rooms/team-a/jira/sites").json()
    assert sites == [{"cloud_id": CLOUD_ID, "name": "shop", "url": "https://shop.atlassian.net"}]
    boards = browser.get(f"/api/rooms/team-a/jira/boards?cloud_id={CLOUD_ID}").json()
    assert [b["name"] for b in boards] == ["SHOP board", "BIG board"]

    chosen = browser.put(
        "/api/rooms/team-a/jira/board",
        json={"cloud_id": CLOUD_ID, "board_id": 1},
        headers={"origin": BASE},
    )
    assert chosen.status_code == 200
    jira = chosen.json()["settings"]["jira"]
    assert jira["site"] == {
        "cloud_id": CLOUD_ID,
        "name": "shop",
        "url": "https://shop.atlassian.net",
    }
    assert jira["board"] == {"id": 1, "name": "SHOP board"}


def test_jc13_refresh_tokens_are_stored_encrypted(japp, atlassian, jira_settings):
    browser = owner_browser(japp)
    connect_through_consent(browser)

    db = sqlite3.connect(jira_settings.database_path)
    stored = db.execute("SELECT jira_token FROM rooms WHERE slug = 'team-a'").fetchone()[0]
    dump = "\n".join(db.iterdump())
    db.close()

    assert stored
    for token in atlassian.refresh_tokens:
        assert token not in dump
    assert japp.state.jira.cipher.open(stored) in atlassian.refresh_tokens


def test_cancelled_consent_returns_to_settings(japp):
    done = connect_through_consent(owner_browser(japp), approve="0")
    assert done.headers["location"] == "/r/team-a/settings?jira=denied"
    assert japp.state.store.get("team-a").jira.connected is False


def test_only_the_owner_connects_or_reads_the_jira_settings(japp, atlassian):
    connect(japp, atlassian)
    for identity, status in ((DELEGATE, 403), (None, 401)):
        browser = TestClient(japp, base_url=BASE)
        if identity:
            browser.cookies.set("sp_session", japp.state.auth.session_value(identity))
        assert (
            browser.get("/auth/atlassian/login?room=team-a", follow_redirects=False).status_code
            == status
        )
        assert browser.get("/api/rooms/team-a/jira/sites").status_code == status
        assert (
            browser.delete("/api/rooms/team-a/jira", headers={"origin": BASE}).status_code == status
        )
        assert (
            browser.put(
                "/api/rooms/team-a/jira/board",
                json={"cloud_id": CLOUD_ID, "board_id": 2},
                headers={"origin": BASE},
            ).status_code
            == status
        )


def test_a_board_must_exist_on_the_site(japp, atlassian):
    connect(japp, atlassian)
    browser = owner_browser(japp)
    for body in ({"cloud_id": "other-site", "board_id": 1}, {"cloud_id": CLOUD_ID, "board_id": 99}):
        response = browser.put("/api/rooms/team-a/jira/board", json=body, headers={"origin": BASE})
        assert response.status_code == 422


def test_callback_state_must_match(japp):
    browser = owner_browser(japp)
    browser.get("/auth/atlassian/login?room=team-a", follow_redirects=False)
    forged = browser.get("/auth/atlassian/callback?code=x&state=forged", follow_redirects=False)
    assert forged.status_code == 400


def test_hs05_atlassian_sign_in_returns_to_an_https_callback(settings, tmp_path):
    base = "https://poker.example.com"
    https = Settings(
        **{
            **settings.__dict__,
            "base_url": base,
            "atlassian": atlassian_config(base, "cid", "secret"),
        }
    )
    app = create_app(settings=https, static_dir=tmp_path)
    app.state.store.create(RoomRecord("team-a", OWNER.key, OWNER.label))
    browser = TestClient(app, base_url=base)
    browser.cookies.set("sp_session", app.state.auth.session_value(OWNER))

    start = browser.get("/auth/atlassian/login?room=team-a", follow_redirects=False)

    location = urlsplit(start.headers["location"])
    query = parse_qs(location.query)
    assert (location.scheme, location.netloc) == ("https", "auth.atlassian.com")
    assert query["redirect_uri"] == ["https://poker.example.com/auth/atlassian/callback"]
    assert query["audience"] == ["api.atlassian.com"]
    assert query["prompt"] == ["consent"]
    assert len(query["scope"][0].split()) == 7
    assert "Secure" in start.headers["set-cookie"]


# The ticket description


def test_rendered_descriptions_are_sanitized():
    dirty = (
        '<p onclick="steal()">Hi <script>alert(1)</script><a href="javascript:x">x</a>'
        '<a href="https://example.com">ok</a><img src=x onerror=y><iframe></iframe></p>'
    )
    cleaned = clean(dirty)

    assert "script" not in cleaned
    assert "onclick" not in cleaned and "onerror" not in cleaned
    assert "javascript:" not in cleaned
    assert "<img" not in cleaned and "<iframe" not in cleaned
    assert '<a href="https://example.com" rel="noopener noreferrer nofollow">ok</a>' in cleaned


# When a session ends


def test_a_room_left_empty_for_15_minutes_starts_a_fresh_session(jclient, japp, atlassian, clock):
    connect(japp, atlassian)
    with facilitator(jclient) as ws:
        ready(ws)
        reveal_and_confirm(ws)
        state(ws, lambda s: s["counters"]["session"]["tickets"] == 1)

    clock.advance(10 * 60)
    with facilitator(jclient) as ws:  # back within 15 minutes: the same session
        snap = ready(ws)
        assert snap["counters"]["session"]["tickets"] == 1

    clock.advance(15 * 60)
    with facilitator(jclient) as ws:
        snap = ready(ws)

    assert snap["counters"]["session"] == {"tickets": 0, "points": 0}
    assert snap["ticket"]["key"] == "SHOP-138"  # SHOP-134 now has an estimate in Jira
    assert snap["counters"]["backlog"] == {"estimated": 5, "total": 12, "points": 21}
