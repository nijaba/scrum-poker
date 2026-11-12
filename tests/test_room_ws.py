"""Room engine over the WebSocket endpoint, at Integration level.

Cases RE-01, RE-06, RC-01, RC-02, RC-03, RS-01, RS-02, RS-03, RX-01.
The facilitator is the room's owner, signed in; see test_rooms_api.py for delegates.
"""

import pytest

from app.room.scales import FIBONACCI
from tests.identities import OWNER, headers, open_ws

ROOM = "/ws/rooms/team-a"


def until(ws, predicate, seen=None):
    """Read messages until one matches. Every message read is added to `seen`."""
    while True:
        msg = ws.receive_json()
        if seen is not None:
            seen.append(msg)
        if predicate(msg):
            return msg


def state(predicate=lambda s: True):
    return lambda m: m["type"] == "state" and predicate(m)


def join(ws, pid, name):
    ws.send_json({"type": "join", "player_id": pid, "name": name})
    return until(ws, state(lambda s: s["you"]["seated"]))


def voted(n):
    return state(lambda s: sum(p["voted"] for p in s["players"]) == n)


def card_labels(snap):
    return [c["label"] for c in snap["scale"]["cards"]]


@pytest.fixture
def facilitator(client):
    with open_ws(client, ROOM, OWNER) as ws:
        join(ws, "f1", "Fay")
        yield ws


def test_re01_votes_stay_hidden_from_every_client(client, facilitator):
    seen = {"f1": [], "p1": [], "p2": [], "p3": []}
    with (
        client.websocket_connect(ROOM) as p1,
        client.websocket_connect(ROOM) as p2,
        client.websocket_connect(ROOM) as p3,
    ):
        players = {"p1": p1, "p2": p2, "p3": p3}
        for pid, ws in players.items():
            join(ws, pid, pid.upper())
        for pid, card in [("p1", "3"), ("p2", "5"), ("p3", "8")]:
            players[pid].send_json({"type": "vote", "card": card})
            until(players[pid], state(lambda s, c=card: s["you"]["vote"] == c), seen[pid])

        for pid, ws in [("f1", facilitator), *players.items()]:
            last = seen[pid][-1] if seen[pid] else None
            snap = last if last and voted(3)(last) else until(ws, voted(3), seen[pid])
            assert [p["voted"] for p in snap["players"]] == [False, True, True, True]

    own = {"p1": "3", "p2": "5", "p3": "8"}
    for pid, messages in seen.items():
        for msg in messages:
            assert msg["round"]["state"] == "voting"
            assert "votes" not in msg["round"]
            assert all("card" not in p for p in msg["players"])
            assert msg["you"]["vote"] in (None, own.get(pid))


def test_re06_player_cannot_send_facilitator_commands(client, facilitator):
    with client.websocket_connect(ROOM) as p1:
        join(p1, "p1", "Ana")
        p1.send_json({"type": "vote", "card": "5"})
        until(p1, voted(1))

        for command in ["reveal", "restart", "skip", "rewind", "reset", "start_countdown"]:
            p1.send_json({"type": command})
            error = until(p1, lambda m: m["type"] == "error")
            assert error["code"] == "forbidden"
        p1.send_json({"type": "confirm", "points": 5})
        assert until(p1, lambda m: m["type"] == "error")["code"] == "forbidden"

        p1.send_json({"type": "vote", "card": "8"})
        snap = until(p1, state(lambda s: s["you"]["vote"] == "8"))
        assert snap["round"]["state"] == "voting"
        assert snap["ticket"]["key"] == "SHOP-134"


def test_rc01_countdown_runs_30_seconds_on_every_screen(client, facilitator):
    with client.websocket_connect(ROOM) as p1:
        join(p1, "p1", "Ana")
        facilitator.send_json({"type": "start_countdown"})

        for ws in (facilitator, p1):
            snap = until(ws, state(lambda s: s["countdown"]["running"]))
            assert snap["countdown"]["duration"] == 30
            assert snap["countdown"]["remaining"] == 30


def test_rc02_countdown_set_to_45_seconds(client, facilitator):
    facilitator.send_json({"type": "set_timer", "seconds": 45})
    until(facilitator, state(lambda s: s["timer_seconds"] == 45))
    facilitator.send_json({"type": "start_countdown"})

    snap = until(facilitator, state(lambda s: s["countdown"]["running"]))
    assert snap["countdown"]["duration"] == 45


def test_rc03_expiry_signals_times_up_and_keeps_cards_hidden(client, clock, facilitator):
    with client.websocket_connect(ROOM) as p1:
        join(p1, "p1", "Ana")
        p1.send_json({"type": "vote", "card": "5"})
        until(facilitator, voted(1))
        facilitator.send_json({"type": "start_countdown"})
        until(p1, state(lambda s: s["countdown"]["running"]))

        clock.advance(30)

        for ws in (facilitator, p1):
            snap = until(ws, state(lambda s: s["countdown"]["time_up"]))
            assert snap["round"]["state"] == "voting"
            assert all("card" not in p for p in snap["players"])
        assert snap["you"]["vote"] == "5"


def owner_sets_scale(client, scale):
    response = client.patch(
        "/api/rooms/team-a", json={"scale": scale}, headers=headers(client.app, OWNER)
    )
    assert response.status_code == 200, response.text


def test_rs01_players_see_fibonacci_cards(client, facilitator):
    owner_sets_scale(client, {"kind": "fibonacci"})
    with client.websocket_connect(ROOM) as p1:
        snap = join(p1, "p1", "Ana")
        assert card_labels(snap) == list(FIBONACCI)


def test_rs02_tshirt_sizes_confirm_with_the_mapped_value(client, facilitator, jira):
    owner_sets_scale(client, {"kind": "tshirt", "mapping": {"S": 2, "M": 3, "L": 5}})
    with client.websocket_connect(ROOM) as p1:
        snap = until(p1, state(lambda s: s["scale"]["kind"] == "tshirt"))
        assert card_labels(snap) == ["S", "M", "L", "?"]
        join(p1, "p1", "Ana")
        p1.send_json({"type": "vote", "card": "M"})
        until(facilitator, voted(1))

        facilitator.send_json({"type": "reveal"})
        until(facilitator, state(lambda s: s["round"]["state"] == "revealed"))
        facilitator.send_json({"type": "confirm", "points": "M"})

        snap = until(p1, state(lambda s: s["ticket"]["key"] == "SHOP-138"))
        assert snap["counters"]["session"] == {"tickets": 1, "points": 3}
        assert jira.writes == [("SHOP-134", 3.0)]


def test_rs03_custom_list_shows_exactly_those_cards(client, facilitator):
    cards = ["1", "2", "4", "8", "?"]
    owner_sets_scale(client, {"kind": "custom", "cards": cards})
    with client.websocket_connect(ROOM) as p1:
        snap = until(p1, state(lambda s: s["scale"]["kind"] == "custom"))
        assert card_labels(snap) == cards


def test_rx01_reset_reseats_only_players_who_check_in(client, clock, facilitator):
    with open_ws(client, ROOM, OWNER) as host:  # watches, never joins
        until(host, state())
        with (
            client.websocket_connect(ROOM) as p1,
            client.websocket_connect(ROOM) as p2,
            client.websocket_connect(ROOM) as p3,
            client.websocket_connect(ROOM) as silent,
        ):
            with client.websocket_connect(ROOM) as gone:
                join(gone, "p5", "Gone")
            stayers = {"p1": p1, "p2": p2, "p3": p3}
            for pid, ws in [*stayers.items(), ("p4", silent)]:
                join(ws, pid, pid.upper())
            until(host, state(lambda s: len(s["players"]) == 6))

            host.send_json({"type": "reset"})
            for ws in stayers.values():
                until(ws, lambda m: m["type"] == "check_in")
                ws.send_json({"type": "check_in"})
            until(host, state(lambda s: len(s["players"]) == 3))

            clock.advance(5)
            snap = until(host, state(lambda s: not s["check_in_open"]))
            assert sorted(p["id"] for p in snap["players"]) == ["p1", "p2", "p3"]
            assert all(p["connected"] for p in snap["players"])


def test_failed_write_keeps_the_room_on_the_ticket(client, facilitator, jira):
    jira.fail_with = "Jira said no"
    facilitator.send_json({"type": "vote", "card": "5"})
    until(facilitator, voted(1))
    facilitator.send_json({"type": "reveal"})
    until(facilitator, state(lambda s: s["round"]["state"] == "revealed"))

    facilitator.send_json({"type": "confirm", "points": 5})
    error = until(facilitator, lambda m: m["type"] == "error")
    assert error["code"] == "write_failed"

    jira.fail_with = None
    facilitator.send_json({"type": "confirm", "points": 5})
    snap = until(facilitator, state(lambda s: s["ticket"]["key"] == "SHOP-138"))
    assert snap["counters"]["session"] == {"tickets": 1, "points": 5}


def test_bad_messages_get_an_error(client):
    with client.websocket_connect(ROOM) as ws:
        until(ws, state())
        ws.send_text("not json")
        assert until(ws, lambda m: m["type"] == "error")["code"] == "invalid_message"
        ws.send_json({"type": "launch"})
        assert until(ws, lambda m: m["type"] == "error")["code"] == "unknown_command"
        ws.send_json({"type": "vote", "card": "5"})
        assert until(ws, lambda m: m["type"] == "error")["code"] == "not_seated"
