"""The little extras: coffee break, splitting hint, nobody knows, perfect consensus.

Cases EE-01 to EE-07 at Unit level, EE-04 at Integration level.
"""

import pytest

from app.room.errors import CommandError
from app.room.results import compute_results
from app.room.room import Room
from app.room.round import REVEALED
from app.room.scales import custom, fibonacci, tshirt
from tests.fakes import FakeClock
from tests.identities import OWNER, open_ws

ROOM = "/ws/rooms/team-a"


@pytest.fixture
def room(fake_backlog):
    room = Room(fake_backlog, clock=FakeClock())
    for pid, name in [("p1", "Ana"), ("p2", "Ben"), ("p3", "Cy")]:
        room.join(pid, name)
    return room


def seat(room, name, viewer="p2"):
    return next(p for p in room.snapshot_for(viewer)["players"] if p["name"] == name)


def votes(scale, *labels):
    return [scale.card(label) for label in labels]


# Coffee break


def test_ee01_a_break_shows_on_every_screen_and_is_not_a_vote(room):
    room.auto_reveal = True
    room.take_break("p1", True)

    for viewer in ("p1", "p2", "p3"):
        ana = seat(room, "Ana", viewer)
        assert ana["on_break"] is True
        assert ana["voted"] is False
    assert room.snapshot_for("p1")["you"]["on_break"] is True
    assert seat(room, "Ben")["on_break"] is False

    room.vote("p2", "5")
    room.vote("p3", "8")
    assert room.round.state != REVEALED  # auto-reveal still waits for Ana


def test_ee02_voting_or_pressing_again_ends_the_break(room):
    room.take_break("p1", True)
    room.vote("p1", "5")
    assert seat(room, "Ana")["on_break"] is False

    room.take_break("p2", True)
    room.take_break("p2", False)
    assert seat(room, "Ben")["on_break"] is False


def test_ee02_a_reset_clears_the_break(room):
    room.take_break("p1", True)
    room.reset()
    room.check_in("p1", "Ana")
    assert seat(room, "Ana")["on_break"] is False


def test_ee03_watchers_and_strangers_cannot_take_a_break(room):
    room.sit_out("p3")
    with pytest.raises(CommandError):
        room.take_break("p3", True)
    with pytest.raises(CommandError):
        room.take_break("nobody", True)
    with pytest.raises(CommandError):
        room.take_break("p1", "yes")


def test_ee03_sitting_out_ends_the_break(room):
    room.take_break("p1", True)
    room.sit_out("p1")
    room.sit_in("p1")
    assert seat(room, "Ana")["on_break"] is False


def test_ee04_a_break_over_the_socket_reaches_every_screen(client):
    with (
        open_ws(client, ROOM, OWNER) as fay,
        client.websocket_connect(ROOM) as ana,
    ):
        fay.send_json({"type": "join", "player_id": "f1", "name": "Fay"})
        ana.send_json({"type": "join", "player_id": "p1", "name": "Ana"})
        ana.send_json({"type": "vote", "card": "8"})
        ana.send_json({"type": "break", "on": True})

        def ana_on_break(msg):
            return msg["type"] == "state" and any(
                p["name"] == "Ana" and p["on_break"] for p in msg["players"]
            )

        while True:
            msg = fay.receive_json()
            assert "8" not in str(msg.get("players", ""))  # no vote value before reveal
            if ana_on_break(msg):
                break


# Results


def test_ee05_the_highest_card_brings_the_splitting_hint():
    fib = fibonacci()
    assert compute_results(votes(fib, "8", "55"), fib.cards).split_hint is True
    assert compute_results(votes(fib, "8", "34", "?"), fib.cards).split_hint is False

    shirts = tshirt()
    assert compute_results(votes(shirts, "XXL"), shirts.cards).split_hint is True
    assert compute_results(votes(shirts, "XL"), shirts.cards).split_hint is False

    own = custom(["1", "2", "4", "?"])
    assert compute_results(votes(own, "4"), own.cards).split_hint is True

    single = custom(["1", "?"])  # one numeric card: no range to split
    assert compute_results(votes(single, "1"), single.cards).split_hint is False


def test_ee05_the_hint_is_in_the_snapshot(room):
    room.vote("p1", "55")
    room.reveal()
    assert room.snapshot_for("p2")["round"]["results"]["split_hint"] is True


def test_ee06_nobody_knows_when_every_vote_is_a_question_mark():
    fib = fibonacci()
    assert compute_results(votes(fib, "?", "?", "?"), fib.cards).nobody_knows is True
    assert compute_results(votes(fib, "?", "?", "3"), fib.cards).nobody_knows is False
    assert compute_results([], fib.cards).nobody_knows is False
    assert compute_results(votes(fib, "?"), fib.cards).to_dict()["nobody_knows"] is True


def test_ee07_five_matching_numeric_votes_make_a_perfect_consensus():
    fib = fibonacci()
    assert compute_results(votes(fib, *["8"] * 5), fib.cards).perfect is True
    assert compute_results(votes(fib, *["8"] * 6), fib.cards).perfect is True
    assert compute_results(votes(fib, *["8"] * 4), fib.cards).perfect is False
    assert compute_results(votes(fib, *["?"] * 5), fib.cards).perfect is False
    assert compute_results(votes(fib, *["8"] * 4, "5"), fib.cards).perfect is False
    assert compute_results(votes(fib, *["8"] * 5), fib.cards).to_dict()["perfect"] is True
