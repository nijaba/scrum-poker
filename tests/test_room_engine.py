"""Room engine at Unit level: rounds, queue and counters, scales, reset, countdown.

Cases RE-03, RE-04, RE-05, RQ-01 to RQ-06, RS-04, RX-03, RX-04.
"""

import pytest

from app.room.errors import CommandError
from app.room.room import Room
from app.room.round import REVEALED, VOTING
from app.room.scales import custom, tshirt
from tests.fakes import FakeClock

UNESTIMATED = [
    "SHOP-134",
    "SHOP-138",
    "SHOP-139",
]  # the first three of the eight, in rank order


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def room(fake_backlog, clock):
    room = Room(fake_backlog, clock=clock)
    for pid, name in [("p1", "Ana"), ("p2", "Ben"), ("p3", "Cy")]:
        room.join(pid, name)
    return room


def estimate(room, points, card="5"):
    room.vote("p1", card)
    room.reveal()
    room.confirm(points)


# Rounds


def test_re03_latest_vote_counts_and_stays_hidden(room):
    room.vote("p1", "3")
    room.vote("p1", "8")

    other = room.snapshot_for("p2")
    assert other["players"][0] == {
        "id": "p1",
        "name": "Ana",
        "connected": True,
        "voted": True,
        "on_break": False,
    }
    assert "votes" not in other["round"]
    assert "8" not in repr(other["players"])
    assert room.snapshot_for("p1")["you"]["vote"] == "8"

    room.reveal()
    assert room.snapshot_for("p2")["players"][0]["card"] == "8"


def test_re04_vote_after_reveal_is_rejected(room):
    room.vote("p1", "3")
    room.reveal()

    with pytest.raises(CommandError) as err:
        room.vote("p2", "5")
    assert err.value.code == "voting_closed"
    assert room.round.state == REVEALED
    assert "p2" not in room.round.votes


def test_re05_restart_clears_cards_and_reopens_voting(room):
    room.vote("p1", "3")
    room.vote("p2", "5")
    room.reveal()

    room.restart()

    assert room.round.state == VOTING
    assert room.round.votes == {}
    room.vote("p3", "8")


def test_unknown_card_is_rejected(room):
    with pytest.raises(CommandError):
        room.vote("p1", "99")


def test_unseated_player_cannot_vote(room):
    with pytest.raises(CommandError):
        room.vote("stranger", "3")


# Queue and counters


def test_rq01_queue_holds_unestimated_tickets_in_rank_order(room, fake_backlog):
    expected = [t["key"] for t in fake_backlog if t["story_points"] is None]

    assert [t.key for t in room.queue.tickets] == expected
    assert len(expected) == 8
    assert expected[:3] == UNESTIMATED
    snap = room.snapshot_for("p1")
    assert snap["ticket"]["key"] == "SHOP-134"
    assert snap["counters"]["backlog"] == {"estimated": 4, "total": 12, "points": 16}
    assert snap["counters"]["session"] == {"tickets": 0, "points": 0}


def test_rq02_confirm_records_points_and_loads_next_ticket(room):
    estimate(room, 5)

    snap = room.snapshot_for("p1")
    assert snap["counters"]["session"] == {"tickets": 1, "points": 5}
    assert snap["counters"]["backlog"] == {"estimated": 5, "total": 12, "points": 21}
    assert snap["ticket"]["key"] == "SHOP-138"
    assert snap["round"]["state"] == VOTING


def test_rq03_skip_loads_next_ticket_and_keeps_counters(room):
    room.skip()

    snap = room.snapshot_for("p1")
    assert snap["ticket"]["key"] == "SHOP-138"
    assert snap["counters"]["session"] == {"tickets": 0, "points": 0}
    assert snap["counters"]["backlog"] == {"estimated": 4, "total": 12, "points": 16}


def test_rq04_rewind_loads_previous_ticket_with_its_result(room):
    estimate(room, 5)
    room.skip()

    room.rewind()
    snap = room.snapshot_for("p1")
    assert snap["ticket"]["key"] == "SHOP-138"
    assert snap["ticket"]["result"] == {"status": "skipped", "points": None}

    room.rewind()
    snap = room.snapshot_for("p1")
    assert snap["ticket"]["key"] == "SHOP-134"
    assert snap["ticket"]["result"] == {"status": "estimated", "points": 5}


def test_rq05_rewind_replaces_estimate(room):
    estimate(room, 5)
    room.rewind()
    estimate(room, 8)

    snap = room.snapshot_for("p1")
    assert snap["counters"]["session"] == {"tickets": 1, "points": 8}
    assert snap["counters"]["backlog"] == {"estimated": 5, "total": 12, "points": 24}


def test_rq06_rewind_on_first_ticket_changes_nothing(room):
    room.vote("p1", "3")
    before = room.snapshot_for("p1")

    room.rewind()

    assert room.snapshot_for("p1") == before


def test_skip_after_rewind_keeps_the_estimate(room):
    estimate(room, 5)
    room.rewind()
    room.skip()

    assert room.queue.session().points == 5


def test_end_of_queue(room):
    for _ in range(8):
        room.skip()

    snap = room.snapshot_for("p1")
    assert snap["ticket"] is None
    assert snap["queue"]["finished"] is True
    with pytest.raises(CommandError):
        room.skip()
    room.rewind()
    assert room.snapshot_for("p1")["ticket"]["key"] == room.queue.tickets[-1].key


def test_confirm_needs_reveal_and_a_numeric_value(room):
    room.vote("p1", "?")
    with pytest.raises(CommandError):
        room.confirm(5)
    room.reveal()
    with pytest.raises(CommandError):
        room.confirm("?")
    with pytest.raises(CommandError):
        room.confirm(-1)
    assert room.queue.cursor == 0


def test_confirm_with_a_tshirt_label_uses_the_mapped_value(fake_backlog, clock):
    room = Room(fake_backlog, clock=clock, scale=tshirt({"S": 2, "M": 3}))
    room.join("p1", "Ana")
    room.vote("p1", "M")
    room.reveal()

    assert room.confirm("M") == 3
    assert room.queue.session().points == 3


# Scales


def test_rs04_scale_change_applies_to_the_next_round(room):
    room.vote("p1", "3")
    new = custom(["1", "2", "4"])

    room.set_scale(new)
    assert room.round.scale.card("3") is not None  # this round keeps its cards
    assert room.snapshot_for("p1")["next_scale"] == new.to_dict()

    room.reveal()
    room.restart()
    assert room.round.scale == new
    assert room.snapshot_for("p1")["scale"] == new.to_dict()
    assert room.snapshot_for("p1")["next_scale"] is None


def test_scale_change_with_no_votes_applies_now(room):
    new = custom(["1", "2", "4"])

    room.set_scale(new)

    assert room.round.scale == new


# Room reset


def test_rx03_reset_keeps_queue_position_and_session_counters(room):
    estimate(room, 5)
    estimate(room, 3)
    before = room.snapshot_for("p1")

    room.reset()

    after = room.snapshot_for("p1")
    assert after["ticket"]["key"] == before["ticket"]["key"] == "SHOP-139"
    assert after["counters"] == before["counters"]
    assert after["players"] == []


def test_rx04_reset_during_a_vote_clears_cards_and_reopens_voting(room):
    room.vote("p1", "3")
    room.vote("p2", "5")

    room.reset()

    assert room.round.state == VOTING
    assert room.round.votes == {}
    room.check_in("p1", "Ana")
    room.vote("p1", "8")


def test_reset_seats_only_players_who_check_in(room, clock):
    room.reset()
    room.check_in("p1", "Ana")
    room.check_in("p3", "Cy")
    clock.advance(5)
    room.tick()

    assert [p["id"] for p in room.snapshot_for("p1")["players"]] == ["p1", "p3"]
    with pytest.raises(CommandError):
        room.check_in("p2", "Ben")
    room.join("p2", "Ben")  # a later join is seated as a new player
    assert [p["id"] for p in room.snapshot_for("p1")["players"]] == ["p1", "p3", "p2"]


# Countdown and sound


def test_countdown_defaults_to_30_seconds_and_expires_without_revealing(room, clock):
    room.vote("p1", "3")
    room.start_countdown()
    assert room.snapshot_for("p2")["countdown"] == {
        "running": True,
        "duration": 30,
        "remaining": 30,
        "time_up": False,
    }

    clock.advance(12)
    assert room.snapshot_for("p2")["countdown"]["remaining"] == 18
    assert room.tick() is False

    clock.advance(18)
    assert room.tick() is True
    snap = room.snapshot_for("p2")
    assert snap["countdown"] == {"running": False, "duration": 30, "remaining": 0, "time_up": True}
    assert snap["round"]["state"] == VOTING
    assert "card" not in snap["players"][0]


def test_countdown_is_settable(room):
    room.set_timer(45)
    room.start_countdown()
    assert room.snapshot_for("p1")["countdown"]["duration"] == 45

    room.start_countdown(10)
    assert room.snapshot_for("p1")["countdown"]["duration"] == 10
    with pytest.raises(CommandError):
        room.set_timer(0)


def test_countdown_clears_on_reveal_and_new_ticket(room):
    room.start_countdown()
    room.vote("p1", "5")
    room.reveal()
    assert room.snapshot_for("p1")["countdown"]["running"] is False


def test_sound_setting_is_carried_in_the_state(room):
    assert room.snapshot_for("p1")["sound"] is False
    room.set_sound(True)
    assert room.snapshot_for("p1")["sound"] is True


# Step 2 additions, for the room screens


def test_stop_countdown_clears_it(room):
    room.start_countdown()
    room.stop_countdown()

    assert room.snapshot_for("p1")["countdown"] == {
        "running": False,
        "duration": None,
        "remaining": None,
        "time_up": False,
    }
    assert room.next_deadline() is None


def test_times_up_stays_shown_after_reveal(room, clock):
    room.start_countdown()
    clock.advance(30)
    room.tick()
    room.reveal()

    assert room.snapshot_for("p1")["countdown"]["time_up"] is True
    room.restart()
    assert room.snapshot_for("p1")["countdown"]["time_up"] is False


def test_reveal_stops_a_running_countdown(room):
    room.start_countdown()
    room.reveal()

    countdown = room.snapshot_for("p1")["countdown"]
    assert countdown["running"] is False
    assert countdown["time_up"] is False
    assert room.next_deadline() is None


def test_snapshot_lists_the_next_five_tickets(room):
    up_next = room.snapshot_for("p1")["up_next"]
    assert [t["key"] for t in up_next] == [
        "SHOP-138",
        "SHOP-139",
        "SHOP-142",
        "SHOP-143",
        "SHOP-147",
    ]
    assert up_next[0]["summary"] == "Address autocomplete at checkout"

    for _ in range(7):
        room.skip()
    assert room.snapshot_for("p1")["up_next"] == []


def test_snapshot_carries_your_name(room):
    assert room.snapshot_for("p2")["you"]["name"] == "Ben"
    assert room.snapshot_for(None)["you"]["name"] is None


def test_ticket_url_comes_from_the_backlog(fake_backlog, clock):
    fake_backlog[1]["url"] = "https://example.atlassian.net/browse/SHOP-134"
    room = Room(fake_backlog, clock=clock)

    assert room.snapshot_for(None)["ticket"]["url"] == fake_backlog[1]["url"]
    assert (
        Room([{"key": "X-1", "story_points": None}], clock=clock).snapshot_for(None)["ticket"][
            "url"
        ]
        is None
    )
