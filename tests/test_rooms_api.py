"""Rooms, settings and delegates over HTTP, and the controls they grant in a live room.

Cases AR-06 to AR-13, PK-05, PK-06, at Integration level.
"""

import sqlite3

import pytest
from starlette.websockets import WebSocketDisconnect

from app.store.rooms import RoomRecord
from tests.identities import (
    DELEGATE,
    GH_DELEGATE,
    GH_OUTSIDER,
    OUTSIDER,
    OWNER,
    headers,
    open_ws,
)


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


def api(client, method, path, identity=None, **kw):
    return client.request(method, path, headers=headers(client.app, identity), **kw)


def patch(client, slug, body, identity=OWNER):
    return api(client, "PATCH", f"/api/rooms/{slug}", identity, json=body)


def add_delegates(client, slug, *entries):
    body = {"delegates": [{"provider": p, "identifier": i} for p, i in entries]}
    response = patch(client, slug, body)
    assert response.status_code == 200, response.text
    return response.json()


def controls(ws):
    """Does this connection have the session controls? Ask the server by trying one."""
    ws.send_json({"type": "stop_countdown"})
    while True:
        msg = ws.receive_json()
        if msg["type"] == "error":
            assert msg["code"] == "forbidden"
            return False
        if msg["type"] == "state":
            return msg["you"]["role"] == "facilitator"


# Creating rooms


def test_ar06_owner_creates_a_room_that_opens_at_its_link(client):
    created = api(client, "POST", "/api/rooms", OWNER, json={"slug": "team-z"})

    assert created.status_code == 201
    assert created.json()["slug"] == "team-z"
    assert client.get("/r/team-z").status_code == 200
    info = api(client, "GET", "/api/rooms/team-z").json()
    assert info == {"slug": "team-z", "access": None}
    with open_ws(client, "/ws/rooms/team-z", OWNER, ("p-own", "Olive")) as ws:
        snap = state(ws, lambda s: s["you"]["seated"])
        assert snap["you"]["role"] == "facilitator"
        assert snap["you"]["access"] == "owner"


def test_ar07_a_taken_name_is_rejected(client):
    response = api(client, "POST", "/api/rooms", OWNER, json={"slug": "team-a"})

    assert response.status_code == 409
    assert "taken" in response.json()["detail"]


@pytest.mark.parametrize("slug", ["", "Team-A", "team a", "-team", "x" * 41, None, 7])
def test_bad_names_are_rejected(client, slug):
    assert api(client, "POST", "/api/rooms", OWNER, json={"slug": slug}).status_code == 422


def test_ar08_pk06_two_rooms_run_independently(client):
    assert api(client, "POST", "/api/rooms", OWNER, json={"slug": "team-b"}).status_code == 201

    with (
        open_ws(client, "/ws/rooms/team-a", OWNER, ("pa", "Ana")) as a,
        open_ws(client, "/ws/rooms/team-b", None, ("pb", "Ben")) as b,
    ):
        state(a, lambda s: s["you"]["seated"])
        state(b, lambda s: s["you"]["seated"])
        a.send_json({"type": "vote", "card": "5"})
        a.send_json({"type": "reveal"})
        snap_a = state(a, lambda s: s["round"]["state"] == "revealed")
        b.send_json({"type": "vote", "card": "8"})
        snap_b = state(b, lambda s: s["players"][0]["voted"])

    assert [p["name"] for p in snap_a["players"]] == ["Ana"]
    assert [p["name"] for p in snap_b["players"]] == ["Ben"]
    assert snap_b["round"]["state"] == "voting"
    assert snap_a["players"][0]["card"] == "5"


def test_rooms_list_shows_owned_and_delegated_rooms(client):
    api(client, "POST", "/api/rooms", OWNER, json={"slug": "team-b"})
    add_delegates(client, "team-b", ("google", "delegate@example.com"))

    owned = api(client, "GET", "/api/rooms", OWNER).json()
    delegated = api(client, "GET", "/api/rooms", DELEGATE).json()

    assert owned == [
        {"slug": "team-a", "access": "owner"},
        {"slug": "team-b", "access": "owner"},
    ]
    assert delegated == [{"slug": "team-b", "access": "delegate"}]
    assert api(client, "GET", "/api/rooms").status_code == 401


# Delegates


def test_ar09_delegate_by_google_email_gets_controls_in_that_room_only(client):
    api(client, "POST", "/api/rooms", OWNER, json={"slug": "team-b"})
    add_delegates(client, "team-a", ("google", "Delegate@Example.com"))

    with open_ws(client, "/ws/rooms/team-a", DELEGATE) as here:
        state(here)
        assert controls(here) is True
    with open_ws(client, "/ws/rooms/team-b", DELEGATE) as there:
        state(there)
        assert controls(there) is False


def test_ar10_delegate_by_github_username_gets_controls_in_that_room_only(client):
    api(client, "POST", "/api/rooms", OWNER, json={"slug": "team-b"})
    add_delegates(client, "team-a", ("github", "Octo-Delegate"))

    with open_ws(client, "/ws/rooms/team-a", GH_DELEGATE) as here:
        state(here)
        assert controls(here) is True
    with open_ws(client, "/ws/rooms/team-b", GH_DELEGATE) as there:
        state(there)
        assert controls(there) is False
    with open_ws(client, "/ws/rooms/team-a", GH_OUTSIDER) as stranger:
        state(stranger)
        assert controls(stranger) is False


def test_ar11_delegate_cannot_change_settings_delegates_or_delete(client):
    add_delegates(client, "team-a", ("google", "delegate@example.com"))

    for body in (
        {"scale": {"kind": "tshirt"}},
        {"timer_seconds": 60},
        {"sound": True},
        {"delegates": []},
        {"slug": "mine-now"},
    ):
        assert patch(client, "team-a", body, DELEGATE).status_code == 403
    assert api(client, "DELETE", "/api/rooms/team-a", DELEGATE).status_code == 403
    assert api(client, "GET", "/api/rooms/team-a", DELEGATE).json() == {
        "slug": "team-a",
        "access": "delegate",
    }
    room = client.app.state.store.get("team-a")
    assert room.scale.kind == "fibonacci"
    assert len(room.delegates) == 1


def test_ar11_delegate_cannot_change_the_scale_over_the_socket(client):
    add_delegates(client, "team-a", ("google", "delegate@example.com"))
    with open_ws(client, "/ws/rooms/team-a", DELEGATE) as ws:
        state(ws)
        ws.send_json({"type": "set_scale", "scale": {"kind": "tshirt"}})
        assert until_type(ws, "error")["code"] == "unknown_command"


def test_ar12_matching_display_name_gives_no_controls(client):
    add_delegates(client, "team-a", ("google", "delegate@example.com"))
    from app.auth.identity import Identity

    impostor = Identity("google", "g-x", DELEGATE.name, email="someone@example.org")

    with open_ws(client, "/ws/rooms/team-a", impostor, ("px", DELEGATE.name)) as ws:
        snap = state(ws, lambda s: s["you"]["seated"])
        assert snap["you"]["role"] == "player"
        assert controls(ws) is False
    with open_ws(client, "/ws/rooms/team-a", OUTSIDER, ("py", DELEGATE.name)) as ws:
        state(ws)
        assert controls(ws) is False


def test_ar13_removed_delegate_loses_controls_at_once(client):
    add_delegates(client, "team-a", ("google", "delegate@example.com"))

    with open_ws(client, "/ws/rooms/team-a", DELEGATE, ("pd", "Dee")) as ws:
        state(ws, lambda s: s["you"]["seated"])
        assert controls(ws) is True

        assert patch(client, "team-a", {"delegates": []}).status_code == 200

        snap = state(ws, lambda s: s["you"]["role"] == "player")
        assert snap["you"]["access"] is None
        assert controls(ws) is False


def test_delegate_entries_are_checked(client):
    for entry in (
        {"provider": "google", "identifier": "not-an-email"},
        {"provider": "github", "identifier": "bad login!"},
        {"provider": "slack", "identifier": "x"},
        "delegate@example.com",
    ):
        assert patch(client, "team-a", {"delegates": [entry]}).status_code == 422


# Settings


def test_owner_reads_and_changes_settings(client):
    response = patch(
        client,
        "team-a",
        {
            "scale": {"kind": "custom", "cards": ["1", "2", "4", "?"]},
            "timer_seconds": 45,
            "sound": True,
        },
    )

    assert response.status_code == 200
    settings = api(client, "GET", "/api/rooms/team-a", OWNER).json()["settings"]
    assert [c["label"] for c in settings["scale"]["cards"]] == ["1", "2", "4", "?"]
    assert settings["timer_seconds"] == 45
    assert settings["sound"] is True
    assert settings["delegates"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"timer_seconds": 0},
        {"timer_seconds": "30"},
        {"sound": "yes"},
        {"scale": {"kind": "custom", "cards": []}},
        {"unknown": 1},
    ],
)
def test_bad_settings_are_rejected(client, body):
    assert patch(client, "team-a", body).status_code == 422


def test_saved_settings_reach_a_live_room(client):
    with open_ws(client, "/ws/rooms/team-a", None, ("p1", "Ana")) as ws:
        state(ws, lambda s: s["you"]["seated"])

        patch(client, "team-a", {"timer_seconds": 45, "sound": True})

        snap = state(ws, lambda s: s["timer_seconds"] == 45)
        assert snap["sound"] is True


def test_session_changes_do_not_change_the_saved_defaults(client):
    with open_ws(client, "/ws/rooms/team-a", OWNER) as ws:
        state(ws)
        ws.send_json({"type": "set_timer", "seconds": 90})
        ws.send_json({"type": "set_sound", "on": True})
        state(ws, lambda s: s["timer_seconds"] == 90 and s["sound"])

        # An unrelated settings change keeps the session's own timer and sound.
        add_delegates(client, "team-a", ("google", "delegate@example.com"))
        snap = state(ws)
        assert (snap["timer_seconds"], snap["sound"]) == (90, True)

    room = client.app.state.store.get("team-a")
    assert (room.timer_seconds, room.sound) == (30, False)


# Rename and delete


def test_renamed_room_keeps_its_old_link_working(client):
    with open_ws(client, "/ws/rooms/team-a", None, ("p1", "Ana")) as ws:
        state(ws, lambda s: s["you"]["seated"])

        response = patch(client, "team-a", {"slug": "alpha"})

        assert response.status_code == 200
        assert response.json()["slug"] == "alpha"
        assert until_type(ws, "moved") == {"type": "moved", "slug": "alpha"}

    old = client.get("/r/team-a", follow_redirects=False)
    assert old.status_code == 308
    assert old.headers["location"] == "/r/alpha"
    settings_page = client.get("/r/team-a/settings", follow_redirects=False)
    assert settings_page.headers["location"] == "/r/alpha/settings"
    assert api(client, "GET", "/api/rooms/team-a").json() == {"slug": "alpha", "access": None}
    with open_ws(client, "/ws/rooms/team-a", None, ("p1", "Ana")) as ws:
        snap = state(ws, lambda s: s["you"]["seated"])
        assert [p["name"] for p in snap["players"]] == ["Ana"]  # the same live room
    assert api(client, "POST", "/api/rooms", OWNER, json={"slug": "team-a"}).status_code == 409


def test_rename_onto_a_taken_name_is_rejected(client):
    api(client, "POST", "/api/rooms", OWNER, json={"slug": "team-b"})
    assert patch(client, "team-a", {"slug": "team-b"}).status_code == 409


def test_deleting_a_room_ends_its_live_session(client):
    with open_ws(client, "/ws/rooms/team-a", None, ("p1", "Ana")) as ws:
        state(ws, lambda s: s["you"]["seated"])

        assert api(client, "DELETE", "/api/rooms/team-a", OWNER).status_code == 204

        assert until_type(ws, "deleted") == {"type": "deleted"}

    assert client.get("/r/team-a").status_code == 404
    assert api(client, "GET", "/api/rooms/team-a").status_code == 404


@pytest.mark.parametrize("slug", ["nobody-here", "Not_A_Slug"])
def test_unknown_rooms_do_not_open(client, slug):
    assert client.get(f"/r/{slug}").status_code == 404
    # The socket is accepted, then closed with 4404, so a browser learns why. A socket
    # refused before it is accepted reaches the browser as a bare HTTP 403 and close
    # code 1006, which looks like a dropped connection, and the page retries forever.
    with open_ws(client, f"/ws/rooms/{slug}") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4404


# Cross-site requests


def test_writes_from_another_site_are_refused(client):
    evil = {**headers(client.app, OWNER), "origin": "https://evil.example"}
    assert client.patch("/api/rooms/team-a", json={"sound": True}, headers=evil).status_code == 403
    assert client.delete("/api/rooms/team-a", headers=evil).status_code == 403
    assert client.post("/api/rooms", json={"slug": "x"}, headers=evil).status_code == 403
    assert client.post("/api/player", json={"name": "x"}, headers=evil).status_code == 403


def test_writes_must_be_json(client):
    response = client.post(
        "/api/rooms",
        content="slug=x",
        headers={**headers(client.app, OWNER), "content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 415


# What the SQLite file holds


def test_pk05_the_file_holds_no_votes_results_or_counters(client, settings):
    with open_ws(client, "/ws/rooms/team-a", OWNER, ("p-own", "Olive")) as ws:
        state(ws, lambda s: s["you"]["seated"])
        ws.send_json({"type": "vote", "card": "13"})
        ws.send_json({"type": "reveal"})
        state(ws, lambda s: s["round"]["state"] == "revealed")
        ws.send_json({"type": "confirm", "points": "13"})
        snap = state(ws, lambda s: s["counters"]["session"]["tickets"] == 1)
        assert snap["counters"]["session"]["points"] == 13

    db = sqlite3.connect(settings.database_path)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"rooms", "delegates", "slug_aliases"}
    columns = {r[1] for r in db.execute("PRAGMA table_info(rooms)")}
    assert columns == {
        "slug",
        "owner_provider",
        "owner_subject",
        "owner_label",
        "scale",
        "timer_seconds",
        "sound",
        "created_at",
        # The room's Jira connection is part of its definition (design: What is stored where).
        "jira_token",
        "jira_email",
        "jira_cloud_id",
        "jira_site_url",
        "jira_site_name",
        "jira_board_id",
        "jira_board_name",
        "auto_reveal",
        "queue_filter",  # a setting: which tickets the queue takes
    }
    dump = "\n".join(db.iterdump())
    db.close()
    for leaked in ("SHOP-134", "p-own", "Olive", "revealed"):
        assert leaked not in dump


def test_records_are_plain_definitions():
    record = RoomRecord("x", OWNER.key, OWNER.label)
    assert record.access(OWNER) == "owner"
    assert record.access(DELEGATE) is None
