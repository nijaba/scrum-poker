"""The player cookie, the pages and app configuration, at Integration level.

The browser flows these support (AR-14 to AR-16) are proved end to end in tests/e2e.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.players import COOKIE, decode_player
from app.store.rooms import RoomRecord
from tests.identities import OWNER, open_ws

ROOM = "/ws/rooms/team-a"


def connect(client, url=ROOM):
    """Open a room socket with the player cookie.

    Starlette's test client does not send its cookies on WebSockets; browsers do.
    """
    value = client.cookies.get(COOKIE)
    headers = {"cookie": f"{COOKIE}={value}"} if value else {}
    return client.websocket_connect(url, headers=headers)


def state(ws, predicate):
    while True:
        msg = ws.receive_json()
        if msg["type"] == "state" and predicate(msg):
            return msg


def test_no_cookie_means_no_player(client):
    assert client.get("/api/player").status_code == 404


def test_naming_sets_a_year_long_cookie_with_name_and_random_id(client):
    response = client.post("/api/player", json={"name": "  Ana  "})

    assert response.status_code == 200
    player = response.json()
    assert player["name"] == "Ana"
    assert len(player["id"]) >= 16
    header = response.headers["set-cookie"]
    assert f"{COOKIE}=" in header
    assert "Max-Age=31536000" in header
    assert "HttpOnly" in header
    assert "samesite=lax" in header.lower()
    assert client.get("/api/player").json() == player


def test_renaming_keeps_the_id(client):
    first = client.post("/api/player", json={"name": "Ana"}).json()
    second = client.post("/api/player", json={"name": "Anna"}).json()

    assert second == {"id": first["id"], "name": "Anna"}


def test_two_browsers_get_different_ids(client):
    other = TestClient(client.app, base_url="http://localhost")
    a = client.post("/api/player", json={"name": "Ana"}).json()
    b = other.post("/api/player", json={"name": "Ana"}).json()

    assert a["id"] != b["id"]


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "   "}, {"name": "x" * 41}, {}, []])
def test_bad_names_are_rejected(client, body):
    assert client.post("/api/player", json=body).status_code == 422


# HS-04 (Secure cookies outside localhost) is in test_auth.py.


def test_cookie_is_not_secure_on_localhost(client):
    header = client.post("/api/player", json={"name": "Ana"}).headers["set-cookie"]
    assert "Secure" not in header


def test_tampered_cookie_is_ignored(client):
    client.cookies.set(COOKIE, "not-base64!")
    assert client.get("/api/player").status_code == 404
    assert decode_player("e30") is None  # "{}"


def test_websocket_seats_the_player_from_the_cookie(client):
    player = client.post("/api/player", json={"name": "Ana"}).json()

    with connect(client) as ws:
        snap = state(ws, lambda s: s["you"]["seated"])
        assert snap["you"]["player_id"] == player["id"]
        assert snap["you"]["name"] == "Ana"
        assert snap["you"]["role"] == "player"

    with connect(client) as ws:  # reconnect: the same seat
        snap = state(ws, lambda s: s["you"]["seated"])
        assert [p["id"] for p in snap["players"]] == [player["id"]]


def test_websocket_without_a_cookie_watches_until_it_joins(client):
    with client.websocket_connect(ROOM) as ws:
        snap = ws.receive_json()
        assert snap["you"]["seated"] is False
        assert snap["players"] == []


def test_join_without_a_payload_uses_the_cookie_after_a_reset(client):
    player = client.post("/api/player", json={"name": "Ana"}).json()
    with open_ws(client, ROOM, OWNER, (player["id"], player["name"])) as ws:
        state(ws, lambda s: s["you"]["seated"])
        ws.send_json({"type": "reset"})
        state(ws, lambda s: not s["you"]["seated"])
        ws.send_json({"type": "join"})
        snap = state(ws, lambda s: s["you"]["seated"])
        assert snap["you"]["name"] == "Ana"


def test_room_pages_serve_the_single_page_app(settings, tmp_path):
    static = tmp_path / "built"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>Scrum poker</title>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    app = create_app(settings=settings, static_dir=static)
    app.state.store.create(RoomRecord("team-a", OWNER.key, OWNER.label))
    client = TestClient(app, base_url="http://localhost")

    for path in ["/", "/r/team-a", "/r/team-a/settings"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "Scrum poker" in response.text
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/r/Not_A_Slug").status_code == 404
    assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("favicon.svg", "image/svg+xml"),
        ("favicon.ico", "image/vnd.microsoft.icon"),
        ("apple-touch-icon.png", "image/png"),
    ],
)
def test_favicons_are_served_from_the_built_front_end(settings, tmp_path, name, kind):
    static = tmp_path / "built"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Scrum poker</title>")
    (static / name).write_bytes(b"icon")
    client = TestClient(create_app(settings=settings, static_dir=static))

    response = client.get(f"/{name}")

    assert response.status_code == 200
    assert response.content == b"icon"
    assert response.headers["content-type"].split(";")[0] in (kind, "image/x-icon")
    assert "max-age" in response.headers["cache-control"]


def test_missing_favicon_is_a_404(settings, tmp_path):
    client = TestClient(create_app(settings=settings, static_dir=tmp_path))

    assert client.get("/favicon.ico").status_code == 404


def test_pages_explain_when_the_front_end_is_not_built(settings, tmp_path):
    app = create_app(settings=settings, static_dir=tmp_path / "missing")
    app.state.store.create(RoomRecord("team-a", OWNER.key, OWNER.label))
    response = TestClient(app, base_url="http://localhost").get("/r/team-a")

    assert response.status_code == 503
    assert "npm run build" in response.text


def test_fake_backlog_from_the_environment_feeds_the_fake_jira(monkeypatch, tmp_path, settings):
    from app.config import FAKE_JIRA_PATH, Settings, atlassian_config

    path = tmp_path / "backlog.json"
    path.write_text(json.dumps([{"key": "X-1", "summary": "One", "story_points": None}]))
    monkeypatch.setenv("SCRUM_POKER_FAKE_BACKLOG", str(path))
    jira = atlassian_config("http://localhost", "fake", "fake", "http://localhost" + FAKE_JIRA_PATH)
    app = create_app(
        settings=Settings(**{**settings.__dict__, "atlassian": jira, "fake_jira": True})
    )

    issues = app.state.fake_atlassian.boards[1]["issues"]
    assert [i["key"] for i in issues] == ["X-1"]
