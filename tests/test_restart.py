"""Restarting the app during a live session: case PK-04, at Integration level.

A restart is a new app on the same SQLite file. Jira keeps what it was told,
so the same FakeJira stands in for Jira on both sides of the restart.
"""

from fastapi.testclient import TestClient

from app.main import create_app
from app.store.rooms import RoomRecord
from tests.identities import BASE, OWNER, open_ws

FAY = ("p-fay", "Fay")
ANA = ("p-ana", "Ana")


def state(ws, predicate=lambda s: True):
    while True:
        msg = ws.receive_json()
        if msg["type"] == "state" and predicate(msg):
            return msg


def start(settings, jira, clock, tmp_path):
    static = tmp_path / "static"
    static.mkdir(exist_ok=True)
    (static / "index.html").write_text("<!doctype html><title>Scrum poker</title>")
    return create_app(
        settings=settings, backlog_source=jira, points_writer=jira, clock=clock, static_dir=static
    )


def test_pk04_restart_drops_votes_and_counters_but_jira_keeps_points(
    settings, jira, clock, tmp_path
):
    before = start(settings, jira, clock, tmp_path)
    before.state.store.create(RoomRecord("team-a", OWNER.key, OWNER.label))
    with TestClient(before, base_url=BASE) as client:
        with (
            open_ws(client, "/ws/rooms/team-a", OWNER, FAY) as fay,
            open_ws(client, "/ws/rooms/team-a", None, ANA) as ana,
        ):
            first = state(fay, lambda s: len(s["players"]) == 2)["ticket"]["key"]
            fay.send_json({"type": "vote", "card": "5"})
            ana.send_json({"type": "vote", "card": "5"})
            fay.send_json({"type": "reveal"})
            state(fay, lambda s: s["round"]["state"] == "revealed")
            fay.send_json({"type": "confirm", "points": "5"})
            snap = state(fay, lambda s: s["counters"]["session"]["tickets"] == 1)
            second = snap["ticket"]["key"]
            ana.send_json({"type": "vote", "card": "8"})  # a vote in flight on the next ticket
            state(fay, lambda s: any(p["voted"] for p in s["players"]))
    # The app stops: its lifespan closes the rooms and the store.

    after = start(settings, jira, clock, tmp_path)
    with TestClient(after, base_url=BASE) as client:
        assert client.get("/api/rooms/team-a").status_code == 200  # the room is still there
        with open_ws(client, "/ws/rooms/team-a", None, ANA) as ana:
            snap = state(ana, lambda s: s["you"]["seated"] and s["backlog"]["state"] == "ready")

    assert snap["counters"]["session"] == {"tickets": 0, "points": 0}
    assert snap["you"]["vote"] is None
    assert not any(p["voted"] for p in snap["players"])
    assert [p["name"] for p in snap["players"]] == ["Ana"]
    # Jira kept the confirmed points, so the queue starts after that ticket.
    assert (first, 5) in jira.writes
    assert snap["ticket"]["key"] == second
    assert snap["counters"]["backlog"]["estimated"] == 5
