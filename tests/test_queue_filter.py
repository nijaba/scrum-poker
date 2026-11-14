# ruff: noqa: F811  (the Jira fixtures are imported from test_jira)
"""The queue filter: which backlog tickets a room's sessions walk through.

Cases QF-01 to QF-05 at Unit level, QF-06 to QF-09 at Integration level.
"""

import sqlite3

import pytest

from app.jira.client import _estimable
from app.jira.fake_atlassian import _issue
from app.room.queue import Queue
from app.room.queue_filter import QueueFilter
from app.room.room import Room
from app.store.rooms import SCHEMA, Delegate, RoomRecord, RoomStore
from tests.fakes import FakeClock
from tests.identities import DELEGATE, OWNER, headers, open_ws
from tests.test_jira import (  # noqa: F401  (fixtures)
    atlassian,
    connect,
    facilitator,
    japp,
    jclient,
    jira_settings,
    ready,
    reveal_and_confirm,
    state,
    until_type,
)

DEFAULT = QueueFilter()


def issue(**ticket):
    return _issue({"key": "SHOP-1", **ticket}, 1)


# QF-01: the default is today's filter


def test_qf01_the_default_filter_is_the_long_standing_one():
    assert DEFAULT.is_default
    assert DEFAULT.to_dict() == {
        "subtasks": False,
        "in_progress": False,
        "resolved": False,
        "estimated": False,
        "jql": "",
    }
    assert RoomRecord("r", OWNER.key, OWNER.label).queue_filter == DEFAULT

    assert _estimable(issue(), DEFAULT)
    assert not _estimable(issue(type="Sub-task"), DEFAULT)
    assert not _estimable(issue(type="Epic"), DEFAULT)
    assert not _estimable(issue(status="In Progress"), DEFAULT)
    assert not _estimable(issue(status="Done"), DEFAULT)
    assert not _estimable(issue(resolution="Won't Do"), DEFAULT)
    assert not _estimable(issue(sprint={"id": 1, "state": "future"}), DEFAULT)


def test_qf01_by_default_only_tickets_with_no_estimate_enter_the_queue(fake_backlog):
    queue = Queue.from_backlog(fake_backlog)
    assert len(queue.tickets) == 8
    assert queue.backlog_counters() == {"estimated": 4, "total": 12, "points": 16}


# QF-02 to QF-04: each toggle


def test_qf02_sub_tasks_can_join_but_epics_never_do():
    taken = QueueFilter(subtasks=True)
    assert _estimable(issue(type="Sub-task"), taken)
    assert _estimable(issue(type="Story"), taken)
    assert not _estimable(issue(type="Epic"), taken)


def test_qf03_tickets_in_progress_can_join_but_done_never_does():
    taken = QueueFilter(in_progress=True)
    assert _estimable(issue(status="In Progress"), taken)
    assert _estimable(issue(status="In Review"), taken)
    assert _estimable(issue(), taken)
    assert not _estimable(issue(status="Done"), taken)


def test_qf04_resolved_tickets_can_join_in_a_taken_status():
    taken = QueueFilter(resolved=True)
    assert _estimable(issue(resolution="Won't Do"), taken)
    assert not _estimable(issue(resolution="Done", status="Done"), taken)
    both = QueueFilter(resolved=True, in_progress=True)
    assert _estimable(issue(resolution="Done", status="In Review"), both)


def test_qf04_sprints_always_stay_out():
    everything = QueueFilter(subtasks=True, in_progress=True, resolved=True, estimated=True)
    assert not _estimable(issue(sprint={"id": 1, "state": "active"}), everything)
    assert not _estimable(issue(sprint={"id": 2, "state": "future"}), everything)
    assert _estimable(issue(sprint={"id": 3, "state": "closed"}), everything)


# QF-05: re-estimation


def test_qf05_estimated_tickets_join_the_queue_in_rank_order(fake_backlog):
    queue = Queue.from_backlog(fake_backlog, include_estimated=True)

    assert [t.key for t in queue.tickets] == [t["key"] for t in fake_backlog]
    assert queue.backlog_counters() == {"estimated": 4, "total": 12, "points": 16}

    queue.estimate(8)  # SHOP-131 had 3
    queue.estimate(2)  # SHOP-134 had none
    assert queue.backlog_counters() == {"estimated": 5, "total": 12, "points": 23}
    assert queue.session().tickets == 2 and queue.session().points == 10


def test_qf05_the_jira_estimate_shows_only_after_reveal(fake_backlog):
    room = Room(fake_backlog, clock=FakeClock(), include_estimated=True)
    room.join("p1", "Ana")
    assert room.snapshot_for("p1")["ticket"]["key"] == "SHOP-131"
    assert "estimate" not in room.snapshot_for("p1")["ticket"]

    room.vote("p1", "8")
    room.reveal()
    assert room.snapshot_for("p1")["ticket"]["estimate"] == 3

    room.skip()  # skipping leaves Jira's estimate alone
    assert room.queue.backlog_counters()["points"] == 16


def test_qf05_confirming_a_re_estimate_writes_to_jira(jclient, japp, atlassian):
    connect(japp, atlassian)
    japp.state.store.update("team-a", queue_filter=QueueFilter(estimated=True))

    with facilitator(jclient) as ws:
        snap = ready(ws)
        assert snap["queue"]["length"] == 12
        assert snap["ticket"]["key"] == "SHOP-131"
        reveal_and_confirm(ws, "8")
        snap = state(ws, lambda s: s["ticket"]["key"] == "SHOP-134")

    assert atlassian.estimate(1, "SHOP-131") == 8
    assert snap["counters"]["backlog"] == {"estimated": 4, "total": 12, "points": 21}


# QF-06: extra JQL


def test_qf06_extra_jql_narrows_the_backlog(jclient, japp, atlassian):
    connect(japp, atlassian)
    japp.state.store.update("team-a", queue_filter=QueueFilter(jql="labels = catalog"))

    with facilitator(jclient) as ws:
        snap = ready(ws)

    assert atlassian.last_jql == "labels = catalog"
    assert snap["queue"]["length"] == 3
    assert snap["counters"]["backlog"] == {"estimated": 0, "total": 3, "points": 0}


def test_qf06_a_refused_jql_shows_jiras_message(jclient, japp, atlassian):
    connect(japp, atlassian)
    japp.state.store.update("team-a", queue_filter=QueueFilter(jql="labels ~~ nope"))

    with facilitator(jclient) as ws:
        snap = state(ws, lambda s: s["backlog"]["state"] == "error")

    assert snap["backlog"]["code"] == "jira_bad_filter"
    assert "labels ~~ nope" in snap["backlog"]["message"]


def test_qf06_no_jql_is_sent_by_default(jclient, japp, atlassian):
    connect(japp, atlassian)
    with facilitator(jclient) as ws:
        ready(ws)
    assert atlassian.last_jql is None


# QF-07: saving the filter


def test_qf07_the_owner_saves_the_filter(jclient, japp):
    owner = headers(japp, OWNER)
    body = {"queue_filter": {"estimated": True, "subtasks": True, "jql": " labels = x "}}

    response = jclient.patch("/api/rooms/team-a", json=body, headers=owner)

    assert response.status_code == 200, response.text
    saved = response.json()["settings"]["queue_filter"]
    assert saved == {
        "subtasks": True,
        "in_progress": False,
        "resolved": False,
        "estimated": True,
        "jql": "labels = x",
    }
    assert japp.state.store.get("team-a").queue_filter == QueueFilter(
        subtasks=True, estimated=True, jql="labels = x"
    )
    reopened = RoomStore(japp.state.store.path)
    assert reopened.get("team-a").queue_filter.estimated is True
    reopened.close()


def test_qf07_only_the_owner_saves_it(jclient, japp):
    japp.state.store.update("team-a", delegates=[Delegate("google", DELEGATE.email)])
    delegate = headers(japp, DELEGATE)
    body = {"queue_filter": {"estimated": True}}
    assert jclient.patch("/api/rooms/team-a", json=body, headers=delegate).status_code == 403


@pytest.mark.parametrize(
    "bad",
    [
        "labels = x",
        {"estimated": "yes"},
        {"sprints": True},
        {"jql": 3},
        {"jql": "x" * 501},
    ],
)
def test_qf07_a_bad_filter_is_refused(jclient, japp, bad):
    owner = headers(japp, OWNER)
    response = jclient.patch("/api/rooms/team-a", json={"queue_filter": bad}, headers=owner)
    assert response.status_code == 422


def test_qf07_older_files_upgrade_with_the_default_filter(tmp_path):
    path = tmp_path / "old.sqlite3"
    db = sqlite3.connect(path)
    db.executescript(SCHEMA + "PRAGMA user_version = 1;")
    db.execute(
        "INSERT INTO rooms VALUES ('old', 'google', 'g', 'o@x.com',"
        ' \'{"kind": "fibonacci", "cards": []}\', 30, 0, \'2026-01-01\')'
    )
    db.commit()
    db.close()

    store = RoomStore(path)
    assert store.get("old").queue_filter == DEFAULT
    store.close()


# QF-08: preview


def preview(client, app, body, who=OWNER, slug="team-a"):
    return client.post(
        f"/api/rooms/{slug}/queue-preview", json=body, headers=headers(app, who) if who else {}
    )


def test_qf08_the_preview_uses_the_unsaved_filter(jclient, japp, atlassian):
    connect(japp, atlassian)

    default = preview(jclient, japp, {"queue_filter": {}}).json()
    again = preview(jclient, japp, {"queue_filter": {"estimated": True}}).json()

    assert default["count"] == 8 and default["total"] == 12
    assert default["tickets"][0] == {
        "key": "SHOP-134",
        "summary": default["tickets"][0]["summary"],
        "type": "Story",
        "status": "To Do",
        "estimate": None,
        "url": "https://shop.atlassian.net/browse/SHOP-134",
    }
    assert again["count"] == 12
    assert again["tickets"][0]["key"] == "SHOP-131"
    assert again["tickets"][0]["estimate"] == 3
    assert japp.state.store.get("team-a").queue_filter == DEFAULT  # nothing saved

    with facilitator(jclient) as ws:  # the session loads what the preview showed
        snap = ready(ws)
    assert snap["queue"]["length"] == default["count"]
    assert snap["ticket"]["key"] == default["tickets"][0]["key"]


def test_qf08_the_preview_lists_at_most_50(jclient, japp, atlassian):
    connect(japp, atlassian, board_id=2)
    found = preview(jclient, japp, {"queue_filter": {}}).json()
    assert found["count"] == 120
    assert [t["key"] for t in found["tickets"]] == [f"BIG-{i}" for i in range(1, 51)]


def test_qf08_only_the_owner_previews(jclient, japp, atlassian):
    connect(japp, atlassian)
    japp.state.store.update("team-a", delegates=[Delegate("google", DELEGATE.email)])
    assert preview(jclient, japp, {"queue_filter": {}}, who=DELEGATE).status_code == 403
    assert preview(jclient, japp, {"queue_filter": {}}, who=None).status_code == 401


def test_qf08_the_preview_shows_a_jql_error(jclient, japp, atlassian):
    connect(japp, atlassian)
    response = preview(jclient, japp, {"queue_filter": {"jql": "labels ~~ nope"}})
    assert response.status_code == 422
    assert "labels ~~ nope" in response.json()["detail"]
    assert preview(jclient, japp, {"queue_filter": {"jql": 4}}).status_code == 422


def test_qf08_the_preview_says_when_jira_is_not_connected(jclient, japp):
    response = preview(jclient, japp, {"queue_filter": {}})
    assert response.status_code == 409


# QF-09: reload between tickets


def save_filter(client, app, **fields):
    response = client.patch(
        "/api/rooms/team-a", json={"queue_filter": fields}, headers=headers(app, OWNER)
    )
    assert response.status_code == 200, response.text


def test_qf09_reload_applies_the_saved_filter_and_keeps_the_session(jclient, japp, atlassian):
    connect(japp, atlassian)
    with facilitator(jclient) as ws:
        ready(ws)
        reveal_and_confirm(ws, "5")  # SHOP-134
        state(ws, lambda s: s["ticket"]["key"] == "SHOP-138")
        ws.send_json({"type": "skip"})  # SHOP-138
        state(ws, lambda s: s["ticket"]["key"] == "SHOP-139")

        save_filter(jclient, japp, estimated=True)
        ws.send_json({"type": "reload_backlog"})
        snap = state(ws, lambda s: s["backlog"]["state"] == "ready" and s["queue"]["length"] == 12)

    assert snap["ticket"]["key"] == "SHOP-131"  # the first ticket with no result yet
    assert snap["counters"]["session"]["tickets"] == 1
    assert snap["counters"]["backlog"] == {"estimated": 5, "total": 12, "points": 21}
    assert [e["key"] for e in snap["summary"]] == ["SHOP-134", "SHOP-138"]


def test_qf09_reload_is_refused_once_someone_has_voted(jclient, japp, atlassian):
    connect(japp, atlassian)
    with facilitator(jclient) as ws:
        ready(ws)
        ws.send_json({"type": "vote", "card": "3"})
        state(ws, lambda s: any(p["voted"] for p in s["players"]))
        ws.send_json({"type": "reload_backlog"})
        error = until_type(ws, "error")
    assert error["code"] == "round_in_progress"


def test_qf09_players_still_cannot_reload(jclient):
    with open_ws(jclient, "/ws/rooms/team-a", None, ("p1", "Ana")) as ws:
        state(ws)
        ws.send_json({"type": "reload_backlog"})
        assert until_type(ws, "error")["code"] == "forbidden"


# QF-12: facilitators learn that a saved filter waits for a reload


def test_qf12_facilitators_see_that_the_filter_changed_until_a_reload(jclient, japp, atlassian):
    connect(japp, atlassian)
    with (
        facilitator(jclient) as ws,
        open_ws(jclient, "/ws/rooms/team-a", None, ("p1", "Ana")) as player,
    ):
        assert ready(ws)["backlog"]["filter_changed"] is False

        save_filter(jclient, japp, estimated=True)
        assert state(ws, lambda s: s["backlog"]["filter_changed"])["queue"]["length"] == 8
        snap = state(player, lambda s: s["backlog"]["state"] == "ready")
        assert "filter_changed" not in snap["backlog"]

        save_filter(jclient, japp)  # back to the filter the session loaded with
        state(ws, lambda s: s["backlog"]["filter_changed"] is False)

        save_filter(jclient, japp, estimated=True)
        state(ws, lambda s: s["backlog"]["filter_changed"])
        ws.send_json({"type": "reload_backlog"})
        snap = state(ws, lambda s: s["queue"]["length"] == 12)
        assert snap["backlog"]["filter_changed"] is False
