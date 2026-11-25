"""Session tools over the WebSocket and the settings API, at Integration level.

Cases RV-01, RV-04, RV-05, RV-07, RP-01, RP-03, SM-01, SM-02, UM-02, UM-09, AR-18.
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


def test_rx06_a_player_cannot_seat_as_another_by_sending_their_id(client):
    """With a player cookie (what the browser always has), the join message's player_id
    is ignored: a client cannot take another player's seat by naming their id. M1."""
    with (
        open_ws(client, ROOM, player=("victim", "Vic")) as victim,
        open_ws(client, ROOM, player=("attacker", "Mal")) as attacker,
    ):
        until(victim, state(lambda s: s["you"]["seated"]))
        until(attacker, state(lambda s: s["you"]["seated"]))
        # The attacker tries to assume the victim's id and rename them.
        attacker.send_json({"type": "join", "player_id": "victim", "name": "Pwned"})
        snap = until(attacker, state(lambda s: s["you"]["seated"]))
        # The attacker stays on their own seat; the victim's name is untouched.
        assert snap["you"]["name"] == "Mal"
        assert sorted(p["name"] for p in snap["players"]) == ["Mal", "Vic"]


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


def test_um08_leaving_by_request_works_when_the_socket_is_down(client):
    with open_ws(client, ROOM, OWNER) as fay:
        join(fay, "f1", "Fay")
        with open_ws(client, ROOM, player=("p1", "Ana")) as ana:
            until(ana, state(lambda s: s["you"]["seated"]))
            until(fay, seated(2))
        # Ana's connection is gone (a phone asleep, a network blip): she shows as away.
        until(fay, state(lambda s: any(not p["connected"] for p in s["players"])))

        response = client.post(
            "/api/rooms/team-a/leave", json={}, headers=headers(client.app, player=("p1", "Ana"))
        )

        assert response.status_code == 204
        snap = until(fay, seated(1))
        assert [p["name"] for p in snap["players"]] == ["Fay"]


def test_um08_leaving_without_a_seat_or_a_live_room_is_harmless(client):
    browser = headers(client.app, player=("p9", "Zed"))
    # No live session yet: nothing is started just to leave it.
    assert client.post("/api/rooms/team-a/leave", json={}, headers=browser).status_code == 204
    assert client.app.state.rooms.running("team-a") is None
    # No player cookie.
    assert (
        client.post("/api/rooms/team-a/leave", json={}, headers=headers(client.app)).status_code
        == 204
    )
    assert client.post("/api/rooms/no-such-room/leave", json={}, headers=browser).status_code == 404


def test_um08_leaving_refuses_other_sites(client):
    response = client.post(
        "/api/rooms/team-a/leave",
        json={},
        headers={**headers(client.app, player=("p1", "Ana")), "origin": "https://evil.example.org"},
    )
    assert response.status_code == 403


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


def rename(client, name, player=("p1", "Ana"), slug="team-a", **extra):
    return client.post(
        f"/api/rooms/{slug}/rename",
        json={"name": name},
        headers={**headers(client.app, player=player), **extra},
    )


def test_um09_renaming_keeps_the_seat_vote_and_role(client):
    from app.players import COOKIE, decode_player

    with (
        open_ws(client, ROOM, OWNER, ("f1", "Fay")) as fay,
        open_ws(client, ROOM, player=("p1", "Ana")) as ana,
    ):
        until(fay, seated(2))
        until(ana, state(lambda s: s["you"]["seated"]))
        ana.send_json({"type": "vote", "card": "5"})
        until(fay, state(lambda s: any(p["voted"] for p in s["players"])))

        response = rename(client, "Annabel")
        assert response.status_code == 200, response.text
        cookie = decode_player(response.cookies.get(COOKIE))
        assert (cookie.id, cookie.name) == ("p1", "Annabel")

        snap = until(fay, state(lambda s: "Annabel" in [p["name"] for p in s["players"]]))
        assert sorted(p["name"] for p in snap["players"]) == ["Annabel", "Fay"]
        assert all(p["voted"] for p in snap["players"] if p["name"] == "Annabel")
        mine = until(ana, state(lambda s: s["you"]["name"] == "Annabel"))
        assert mine["you"]["seated"] and mine["you"]["role"] == "player"

        # A facilitator renames too, and stays the facilitator.
        assert rename(client, "Fayette", player=("f1", "Fay")).status_code == 200
        boss = until(fay, state(lambda s: s["you"]["name"] == "Fayette"))
        assert boss["you"]["role"] == "facilitator"

        # A name another seat holds, in any case or spacing, is refused and changes nothing.
        taken = rename(client, "  annabel ", player=("f1", "Fayette"))
        assert taken.status_code == 409
        assert "Annabel" in taken.json()["detail"]
        assert COOKIE not in taken.cookies


def test_um09_bad_requests_are_refused(client):
    with open_ws(client, ROOM, player=("p1", "Ana")) as ana:
        until(ana, state(lambda s: s["you"]["seated"]))
        assert rename(client, "").status_code == 422
        assert rename(client, "x" * 41).status_code == 422
        no_cookie = client.post(
            "/api/rooms/team-a/rename", json={"name": "Zed"}, headers=headers(client.app)
        )
        assert no_cookie.status_code == 401
        assert rename(client, "Zed", slug="no-such-room").status_code == 404
        assert rename(client, "Zed", origin="https://evil.example.org").status_code == 403


def test_um09_renaming_with_no_live_room_just_updates_the_cookie(client):
    from app.players import COOKIE, decode_player

    response = rename(client, "Zed", player=("p9", "Zoe"))
    assert response.status_code == 200
    assert decode_player(response.cookies.get(COOKIE)).name == "Zed"
    assert client.app.state.rooms.running("team-a") is None  # nothing started for it
