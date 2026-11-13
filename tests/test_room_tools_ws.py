"""Session tools over the WebSocket and the settings API, at Integration level.

Cases RV-01, RV-04, RV-05, RV-07, RP-01, RP-03, SM-01, SM-02, UM-02, AR-18.
The facilitator is the room's owner, signed in.
"""

from tests.identities import OWNER, headers, open_ws

ROOM = "/ws/rooms/team-a"


def until(ws, predicate):
    while True:
        msg = ws.receive_json()
        if predicate(msg):
            return msg


def state(predicate=lambda s: True):
    return lambda m: m["type"] == "state" and predicate(m)


def error(ws):
    return until(ws, lambda m: m["type"] == "error")


def join(ws, pid, name):
    ws.send_json({"type": "join", "player_id": pid, "name": name})
    return until(ws, state(lambda s: s["you"]["seated"]))


def seated(n):
    return state(lambda s: len(s["players"]) == n)


def patch(client, body):
    return client.patch("/api/rooms/team-a", json=body, headers=headers(client.app, OWNER))


def test_rv01_auto_reveal_turns_the_cards_when_the_last_player_votes(client):
    with (
        open_ws(client, ROOM, OWNER) as fay,
        client.websocket_connect(ROOM) as ana,
        client.websocket_connect(ROOM) as ben,
    ):
        join(fay, "f1", "Fay")
        join(ana, "p1", "Ana")
        join(ben, "p2", "Ben")
        until(fay, seated(3))
        fay.send_json({"type": "set_auto_reveal", "on": True})
        until(fay, state(lambda s: s["auto_reveal"]))

        for ws, card in [(fay, "3"), (ana, "5")]:
            ws.send_json({"type": "vote", "card": card})
        snap = until(ben, state(lambda s: sum(p["voted"] for p in s["players"]) == 2))
        assert snap["round"]["state"] == "voting"

        ben.send_json({"type": "vote", "card": "5"})

        for ws in (fay, ana, ben):
            snap = until(ws, state(lambda s: s["round"]["state"] == "revealed"))
            assert snap["round"]["results"]["votes"] == 3


def test_rv04_saved_auto_reveal_reaches_live_and_new_sessions(client):
    assert (
        client.get("/api/rooms/team-a", headers=headers(client.app, OWNER)).json()["settings"][
            "auto_reveal"
        ]
        is False
    )

    with open_ws(client, ROOM, OWNER) as fay:
        join(fay, "f1", "Fay")
        response = patch(client, {"auto_reveal": True})
        assert response.status_code == 200, response.text
        assert response.json()["settings"]["auto_reveal"] is True
        until(fay, state(lambda s: s["auto_reveal"]))

    assert client.app.state.store.get("team-a").auto_reveal is True
    assert patch(client, {"auto_reveal": "yes"}).status_code == 422


def test_rv05_session_toggle_leaves_the_saved_setting_alone(client):
    with open_ws(client, ROOM, OWNER) as fay:
        join(fay, "f1", "Fay")
        fay.send_json({"type": "set_auto_reveal", "on": True})
        until(fay, state(lambda s: s["auto_reveal"]))

        # An unrelated settings change keeps the session's own choice.
        assert patch(client, {"timer_seconds": 45}).status_code == 200
        snap = until(fay, state(lambda s: s["timer_seconds"] == 45))
        assert snap["auto_reveal"] is True

    assert client.app.state.store.get("team-a").auto_reveal is False


def test_rv07_rp03_players_cannot_use_the_new_facilitator_commands(client):
    with client.websocket_connect(ROOM) as ana:
        join(ana, "p1", "Ana")
        for command in [
            {"type": "set_auto_reveal", "on": True},
            {"type": "remove_player", "player_id": "p1"},
            {"type": "jump", "key": "SHOP-142"},
        ]:
            ana.send_json(command)
            assert error(ana)["code"] == "forbidden"


def test_rp01_removing_a_player_updates_every_screen(client):
    with (
        open_ws(client, ROOM, OWNER) as fay,
        client.websocket_connect(ROOM) as ana,
        client.websocket_connect(ROOM) as ben,
    ):
        join(fay, "f1", "Fay")
        join(ana, "p1", "Ana")
        join(ben, "p2", "Ben")
        ben.send_json({"type": "vote", "card": "8"})
        until(
            fay, state(lambda s: len(s["players"]) == 3 and any(p["voted"] for p in s["players"]))
        )

        fay.send_json({"type": "remove_player", "player_id": "p2"})

        snap = until(ana, seated(2))
        assert [p["name"] for p in snap["players"]] == ["Fay", "Ana"]
        assert not any(p["voted"] for p in snap["players"])
        mine = until(ben, state(lambda s: not s["you"]["seated"]))
        assert mine["you"]["removed"] is True

        # Ben can join again from the same browser.
        ben.send_json({"type": "join"})
        assert until(ben, state(lambda s: s["you"]["seated"]))["you"]["removed"] is False


def test_sit_out_and_back_over_the_socket(client):
    with open_ws(client, ROOM, OWNER) as fay, client.websocket_connect(ROOM) as ana:
        join(fay, "f1", "Fay")
        join(ana, "p1", "Ana")
        fay.send_json({"type": "sit_out"})
        snap = until(ana, state(lambda s: s["watchers"]))
        assert [p["name"] for p in snap["players"]] == ["Ana"]
        assert [p["name"] for p in snap["watchers"]] == ["Fay"]
        assert until(fay, state(lambda s: s["you"]["sitting_out"]))["you"]["role"] == "facilitator"

        fay.send_json({"type": "sit_in"})
        until(ana, seated(2))


def test_jump_over_the_socket(client):
    with open_ws(client, ROOM, OWNER) as fay, client.websocket_connect(ROOM) as ana:
        join(fay, "f1", "Fay")
        join(ana, "p1", "Ana")
        fay.send_json({"type": "jump", "key": "SHOP-142"})
        assert until(ana, state(lambda s: s["ticket"]["key"] == "SHOP-142"))
        fay.send_json({"type": "jump", "key": "NOPE-1"})
        assert error(fay)["code"] == "unknown_ticket"


def test_sm01_sm02_summary_goes_to_facilitators_only(client):
    with open_ws(client, ROOM, OWNER) as fay, client.websocket_connect(ROOM) as ana:
        join(fay, "f1", "Fay")
        join(ana, "p1", "Ana")
        assert until(fay, seated(2))["summary"] == []

        for card in ("5", "8"):
            fay.send_json({"type": "vote", "card": "5"})
            ana.send_json({"type": "vote", "card": card})
            until(fay, state(lambda s: sum(p["voted"] for p in s["players"]) == 2))
            fay.send_json({"type": "reveal"})
            until(fay, state(lambda s: s["round"]["state"] == "revealed"))
            fay.send_json({"type": "confirm", "points": card})
            until(fay, state(lambda s: s["round"]["state"] == "voting"))
        fay.send_json({"type": "skip"})

        snap = until(fay, state(lambda s: len(s["summary"]) == 3))
        assert [(e["key"], e["status"], e["points"]) for e in snap["summary"]] == [
            ("SHOP-134", "estimated", 5),
            ("SHOP-138", "estimated", 8),
            ("SHOP-139", "skipped", None),
        ]
        assert snap["summary"][1]["votes"] == [
            {"label": "5", "count": 1},
            {"label": "8", "count": 1},
        ]
        assert snap["summary"][1]["average"] == 6.5
        assert "Ana" not in repr(snap["summary"]) and "Fay" not in repr(snap["summary"])

        player = until(ana, state(lambda s: s["ticket"]["key"] == "SHOP-142"))
        assert "summary" not in player


def test_um02_leaving_over_the_socket_updates_every_screen(client):
    with (
        open_ws(client, ROOM, OWNER) as fay,
        client.websocket_connect(ROOM) as ana,
    ):
        join(fay, "f1", "Fay")
        join(ana, "p1", "Ana")
        until(fay, seated(2))

        ana.send_json({"type": "leave"})

        snap = until(fay, seated(1))
        assert [p["name"] for p in snap["players"]] == ["Fay"]
        mine = until(ana, state(lambda s: not s["you"]["seated"]))
        assert mine["you"]["removed"] is False


def test_ar18_a_taken_name_is_refused_over_the_socket(client):
    with client.websocket_connect(ROOM) as ana:
        join(ana, "p1", "Ana")

        # A second browser types the same name.
        with client.websocket_connect(ROOM) as other:
            until(other, state())
            other.send_json({"type": "join", "player_id": "p2", "name": "ana"})
            err = error(other)
            assert err["code"] == "name_taken"
            assert "Ana" in err["message"]

        # A returning browser whose saved name is taken is told so when it connects.
        with open_ws(client, ROOM, player=("p3", "ANA")) as returning:
            err = until(returning, lambda m: m["type"] == "error")
            assert err["code"] == "name_taken"
            snap = until(returning, state())
            assert snap["you"]["seated"] is False
            assert [p["name"] for p in snap["players"]] == ["Ana"]
