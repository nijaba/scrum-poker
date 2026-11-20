"""Setting up a demo room: cases DR-18 to DR-20 (design.md, "Demo rooms").

DR-19 at Unit level, the others at Integration level.
"""

import pytest

from app.demo.backlog import DemoBacklog
from app.room.ports import BacklogError
from app.room.queue_filter import QueueFilter
from tests.test_demo_rooms import demo, demo_app, new_demo, state, until, visit  # noqa: F401

DEFAULT_QUEUE = 8  # the unestimated tickets of the 12 the default filter takes


def settings_of(client, slug):
    return client.get(f"/api/rooms/{slug}").json()["settings"]


def save(client, slug, body, **kw):
    return client.patch(f"/api/demo/{slug}/settings", json=body, **kw)


def test_dr18_anyone_sets_up_a_demo_room(demo):  # noqa: F811
    slug = new_demo(demo)
    shown = settings_of(demo, slug)
    assert shown["jira"]["connected"] is True
    assert shown["jira"]["site"]["name"] == "Demo Co"
    assert shown["jira"]["board"]["name"] == "SHOP board"
    assert shown["delegates"] == [
        {"provider": "google", "identifier": "dana@example.com", "role": "facilitator"}
    ]
    assert shown["scale"]["kind"] == "fibonacci"

    ws, join = visit(demo, slug)
    with ws:
        ws.send_json(join)
        until(ws, state(lambda s: s["you"]["seated"]))
        body = {
            "scale": {"kind": "tshirt", "mapping": {"S": 2, "M": 3, "L": 5}},
            "timer_seconds": 45,
            "sound": False,
            "auto_reveal": True,
            "queue_filter": {"in_progress": True},
        }
        response = save(demo, slug, body)  # no sign-in
        assert response.status_code == 200, response.text
        assert response.json()["settings"]["queue_filter"]["in_progress"] is True

        snap = until(ws, state(lambda s: s["auto_reveal"] and not s["sound"]))
        assert snap["backlog"]["filter_changed"] is True  # applies at Reload backlog
    after = settings_of(demo, slug)
    assert after["timer_seconds"] == 45 and after["scale"]["kind"] == "tshirt"

    for refused in ({"slug": "mine"}, {"delegates": []}, {"timer_seconds": 0}):
        assert save(demo, slug, refused).status_code == 422
    assert save(demo, "demo-nothere", {"sound": True}).status_code == 404
    foreign = save(demo, slug, {"sound": True}, headers={"origin": "https://evil.example.org"})
    assert foreign.status_code == 403
    assert settings_of(demo, slug)["sound"] is False


# DR-19: the demo backlog follows the queue filter.


def load(chosen: QueueFilter | None = None):
    """What the demo room loads with this filter (load_backlog's sync core, so no event loop
    is needed after the browser tests have run)."""
    return DemoBacklog(lambda: chosen or QueueFilter()).backlog(chosen or QueueFilter())


def keys(tickets):
    return {t["key"] for t in tickets}


def test_dr19_the_default_queue_and_counters_are_as_before():
    tickets = load()
    assert len(tickets) == 12
    assert sum(t["story_points"] is None for t in tickets) == DEFAULT_QUEUE
    assert {"SHOP-151", "SHOP-152", "SHOP-153", "SHOP-154"}.isdisjoint(keys(tickets))


@pytest.mark.parametrize(
    ("toggle", "key"),
    [("subtasks", "SHOP-152"), ("in_progress", "SHOP-153"), ("resolved", "SHOP-154")],
)
def test_dr19_each_choice_adds_its_tickets(toggle, key):
    tickets = load(QueueFilter(**{toggle: True}))
    assert key in keys(tickets) and len(tickets) == 13
    assert "SHOP-151" not in keys(tickets)  # the epic never enters


def test_dr19_simple_jql_narrows_and_other_jql_is_refused():
    assert keys(load(QueueFilter(jql="labels = payments"))) == {"SHOP-142", "SHOP-143", "SHOP-145"}
    assert keys(load(QueueFilter(jql="type in (Bug) AND priority = High"))) == {
        "SHOP-136",
        "SHOP-140",
    }
    assert keys(load(QueueFilter(jql="labels in(payments)"))) == {
        "SHOP-142",
        "SHOP-143",
        "SHOP-145",
    }
    assert keys(load(QueueFilter(jql="  PRIORITY=High   and  type = Bug "))) == {
        "SHOP-136",
        "SHOP-140",
    }
    with pytest.raises(BacklogError) as refused:
        load(QueueFilter(jql="sprint in openSprints()"))
    assert refused.value.code == "jira_bad_filter"
    assert "labels, type, priority, status and key" in str(refused.value)


def test_dr20_the_preview_follows_the_form_without_saving(demo):  # noqa: F811
    slug = new_demo(demo)
    preview = demo.post(
        f"/api/demo/{slug}/queue-preview", json={"queue_filter": {"in_progress": True}}
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["count"] == DEFAULT_QUEUE + 1
    assert "SHOP-153" in {t["key"] for t in data["tickets"]}
    assert settings_of(demo, slug)["queue_filter"]["in_progress"] is False  # not saved

    bad = demo.post(f"/api/demo/{slug}/queue-preview", json={"queue_filter": {"jql": "x ~ y"}})
    assert bad.status_code == 422


def test_dr19_crafted_jql_is_read_at_once():
    import time

    for crafted in (
        "a=" + " " * 497 + "!",
        "a" + " " * 496 + "=a",
        " AND" * 125,
        "key=" + "a " * 248,
    ):
        started = time.perf_counter()
        try:
            load(QueueFilter.from_dict({"jql": crafted}))
        except BacklogError:
            pass
        assert time.perf_counter() - started < 0.05, crafted[:20]
