"""Demo rooms: a private room per visitor, with bots and a made-up backlog.

Cases DR-01 to DR-10. DR-06 and DR-09 at Unit level, the rest at Integration level.
"""

import asyncio
import dataclasses
import random
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.demo.bots import BotMind, ticket_size
from app.demo.rooms import DEMO_IDLE_SECONDS, MAX_DEMO_ROOMS, DemoRooms
from app.main import create_app
from app.room.scales import fibonacci
from app.store.rooms import RoomRecord
from tests.fakes import FakeClock
from tests.identities import BASE, OWNER, headers

BOTS = {"Ada", "Bo", "Cleo", "Dev"}


@pytest.fixture
def demo_app(settings, jira, clock, tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Scrum poker</title>")
    app = create_app(
        settings=dataclasses.replace(settings, demo_rooms=True),
        backlog_source=jira,
        points_writer=jira,
        clock=clock,
        static_dir=static,
    )
    app.state.demo.delay = (0, 0)  # bots act at once
    return app


@pytest.fixture
def demo(demo_app):
    with TestClient(demo_app, base_url=BASE) as client:
        yield client


def until(ws, predicate, limit=500):
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("never happened")


def state(predicate=lambda s: True):
    return lambda m: m["type"] == "state" and predicate(m)


def names(snap):
    return {p["name"] for p in snap["players"]}


def new_demo(client):
    response = client.post("/api/demo", json={})
    assert response.status_code == 201, response.text
    return response.json()["slug"]


def visit(client, slug, name="Vic", pid="v1"):
    ws = client.websocket_connect(f"/ws/rooms/{slug}")
    return ws, {"type": "join", "player_id": pid, "name": name}


def test_dr01_demo_rooms_are_off_by_default(client):
    assert client.post("/api/demo", json={}).status_code == 404
    assert client.get("/api/me").json()["demo_rooms"] is False


def test_dr02_a_demo_room_is_private_in_memory_and_comes_with_bots(demo, demo_app):
    assert demo.get("/api/me").json()["demo_rooms"] is True
    slug = new_demo(demo)

    assert slug.startswith("demo-") and len(slug) == len("demo-") + 8
    assert demo_app.state.store.get(slug) is None  # never stored
    assert new_demo(demo) != slug
    assert demo.get(f"/api/rooms/{slug}").json() == {"slug": slug, "access": None, "demo": True}
    assert demo.get(f"/r/{slug}").status_code == 200
    assert demo.get(f"/r/{slug}/settings").status_code == 404

    ws, join = visit(demo, slug)
    with ws:
        ws.send_json(join)
        snap = until(ws, state(lambda s: s["you"]["seated"] and BOTS <= names(s)))
        assert snap["you"]["role"] == "facilitator"
        assert snap["demo"] is True
        assert snap["sound"] is True
        assert snap["backlog"]["state"] == "ready"
        assert snap["ticket"] is not None


def test_dr03_bots_vote_and_their_cards_stay_hidden(demo):
    slug = new_demo(demo)
    ws, join = visit(demo, slug)
    with ws:
        ws.send_json(join)

        def bots_voted(s):
            return sum(p["voted"] for p in s["players"] if p["name"] in BOTS) == 4

        snap = until(ws, state(bots_voted))
        assert snap["round"]["state"] == "voting"
        assert all("card" not in p for p in snap["players"])
        assert "results" not in snap["round"]


def test_dr04_confirming_writes_to_the_demo_backlog_only(demo, jira):
    slug = new_demo(demo)
    ws, join = visit(demo, slug)
    with ws:
        ws.send_json(join)
        first = until(ws, state(lambda s: s["you"]["seated"]))
        key = first["ticket"]["key"]
        estimated = first["counters"]["backlog"]["estimated"]
        ws.send_json({"type": "vote", "card": "5"})
        ws.send_json({"type": "reveal"})
        until(ws, state(lambda s: s["round"]["state"] == "revealed"))
        ws.send_json({"type": "confirm", "points": 5})

        snap = until(ws, state(lambda s: s["counters"]["session"]["tickets"] == 1))
        assert snap["ticket"]["key"] != key
        assert snap["counters"]["backlog"]["estimated"] == estimated + 1
    assert jira.writes == []


def test_dr05_the_number_of_demo_rooms_is_capped(demo):
    for _ in range(MAX_DEMO_ROOMS):
        new_demo(demo)

    response = demo.post("/api/demo", json={})

    assert response.status_code == 503
    assert "try again later" in response.json()["detail"].lower()


def test_dr06_an_idle_demo_room_ends_and_its_bots_stop():
    async def scenario():
        clock = FakeClock()
        rooms = DemoRooms(clock, delay=(0, 0))
        slug = await rooms.create()
        live = rooms.get(slug)
        bots = rooms.bot_tasks(slug)
        assert len(bots) == 4
        for _ in range(20):
            await asyncio.sleep(0)

        clock.advance(DEMO_IDLE_SECONDS - 1)  # bots alone do not keep it alive...
        for _ in range(20):
            await asyncio.sleep(0)
        assert rooms.get(slug) is live

        clock.advance(1)  # ...and with no person for the whole time, it ends
        for _ in range(50):
            await asyncio.sleep(0)
            if rooms.get(slug) is None and all(t.done() for t in bots):
                break
        assert rooms.get(slug) is None
        assert all(t.done() for t in bots)
        assert live.closed
        await rooms.close()

    # In its own thread: after the browser tests, Playwright keeps an event loop running
    # in this one, and asyncio.run refuses to start inside it.
    with ThreadPoolExecutor(1) as pool:
        pool.submit(asyncio.run, scenario()).result(timeout=30)


def test_dr07_a_removed_bot_stays_out_and_bots_can_be_added_up_to_eight(demo):
    slug = new_demo(demo)
    ws, join = visit(demo, slug)
    with ws:
        ws.send_json(join)
        until(ws, state(lambda s: BOTS <= names(s)))

        ws.send_json({"type": "remove_player", "player_id": "bot-ada"})
        until(ws, state(lambda s: "Ada" not in names(s)))

        added = []
        for _ in range(5):
            response = demo.post(f"/api/demo/{slug}/bots", json={})
            assert response.status_code == 201, response.text
            added.append(response.json()["name"])
        assert "Ada" not in added
        snap = until(ws, state(lambda s: set(added) <= names(s)))
        assert "Ada" not in names(snap)
        assert len(names(snap) - {"Vic"}) == 8

        assert demo.post(f"/api/demo/{slug}/bots", json={}).status_code == 409
    assert demo.post("/api/demo/demo-nothere/bots", json={}).status_code == 404


def test_dr08_bots_check_in_after_a_reset(demo):
    slug = new_demo(demo)
    ws, join = visit(demo, slug)
    with ws:
        ws.send_json(join)
        until(ws, state(lambda s: BOTS <= names(s)))

        ws.send_json({"type": "reset"})
        until(ws, state(lambda s: not s["players"]))

        snap = until(ws, state(lambda s: BOTS <= names(s)))
        assert BOTS <= names(snap)


def test_dr09_bot_votes_sit_near_the_tickets_size():
    scale = fibonacci().to_dict()["cards"]
    numeric = [c["label"] for c in scale if c["value"] is not None]
    rng = random.Random(7)
    minds = [BotMind(name, bias, rng) for name, bias in [("A", -1), ("B", 0), ("C", 1)]]
    questions = 0
    for n in range(300):
        key = f"SHOP-{n}"
        size = ticket_size(key, len(numeric))
        assert 0 <= size < len(numeric)
        for mind in minds:
            card = mind.choose(scale, key)
            if card == "?":
                questions += 1
                continue
            assert card in numeric
            assert abs(numeric.index(card) - size) <= 2
    assert 0 < questions < 300 * 3 * 0.15  # now and then, not often


def test_dr10_stored_rooms_cannot_take_a_demo_name(client):
    owner = headers(client.app, OWNER)
    created = client.post("/api/rooms", json={"slug": "demo-abcd1234"}, headers=owner)
    assert created.status_code == 422

    client.app.state.store.create(RoomRecord("team-b", OWNER.key, OWNER.label))
    renamed = client.patch("/api/rooms/team-b", json={"slug": "demo-x"}, headers=owner)
    assert renamed.status_code == 422
