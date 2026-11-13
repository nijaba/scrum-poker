"""Session tools at Unit level: auto-reveal, sitting out, removing a player, jumping to a
ticket, the vote spread and the session summary.

Cases RR-07, RR-08, RQ-08 to RQ-10, RV-02, RV-03, RV-06, SO-01 to SO-04, SM-03, UM-01.
"""

import pytest

from app.room.errors import CommandError
from app.room.results import compute_results
from app.room.room import Room
from app.room.round import REVEALED, VOTING
from app.room.scales import fibonacci, tshirt
from tests.fakes import FakeClock

QUEUE = [
    "SHOP-134",
    "SHOP-138",
    "SHOP-139",
    "SHOP-142",
    "SHOP-143",
    "SHOP-147",
    "SHOP-149",
    "SHOP-150",
]


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def room(fake_backlog, clock):
    room = Room(fake_backlog, clock=clock)
    for pid, name in [("p1", "Ana"), ("p2", "Ben"), ("p3", "Cy")]:
        room.join(pid, name)
    return room


def table(room, viewer="p1"):
    return [p["name"] for p in room.snapshot_for(viewer)["players"]]


def watchers(room, viewer="p1"):
    return [p["name"] for p in room.snapshot_for(viewer)["watchers"]]


# The spread on reveal


def votes(scale, *labels):
    return [scale.card(label) for label in labels]


def test_rr07_spread_in_scale_order_with_highest_and_lowest():
    scale = fibonacci()
    results = compute_results(votes(scale, "8", "5", "?", "3", "5"), scale.cards)

    assert results.spread == (("3", 1), ("5", 2), ("8", 1), ("?", 1))
    assert (results.high, results.low) == ("8", "3")
    data = results.to_dict()
    assert data["spread"] == [
        {"label": "3", "count": 1},
        {"label": "5", "count": 2},
        {"label": "8", "count": 1},
        {"label": "?", "count": 1},
    ]
    assert (data["high"], data["low"]) == ("8", "3")


def test_rr08_no_highest_or_lowest_when_the_numbers_agree():
    scale = fibonacci()
    assert compute_results(votes(scale, "5", "5", "5"), scale.cards).high is None
    # "?" has no number, so 5 and ? do not make a range either.
    mixed = compute_results(votes(scale, "5", "?"), scale.cards)
    assert (mixed.high, mixed.low) == (None, None)


def test_tshirt_highest_and_lowest_follow_the_mapped_points():
    scale = tshirt({"S": 2, "M": 3, "XL": 8})
    results = compute_results(votes(scale, "M", "XL", "S"), scale.cards)

    assert (results.high, results.low) == ("XL", "S")


def test_reveal_snapshot_carries_the_spread(room):
    room.vote("p1", "3")
    room.vote("p2", "8")
    room.reveal()

    results = room.snapshot_for("p3")["round"]["results"]
    assert results["spread"] == [{"label": "3", "count": 1}, {"label": "8", "count": 1}]
    assert (results["high"], results["low"]) == ("8", "3")


# Jumping to a ticket


def test_rq08_jump_loads_the_ticket_and_leaves_the_others_pending(room):
    room.vote("p1", "5")
    before = room.snapshot_for("p1")["counters"]

    room.jump("SHOP-142")

    snap = room.snapshot_for("p1")
    assert snap["ticket"]["key"] == "SHOP-142"
    assert snap["round"]["state"] == VOTING
    assert snap["you"]["vote"] is None
    assert snap["counters"] == before
    for key in QUEUE[:3]:
        assert room.queue.results[key].status == "pending"
    assert snap["queue"]["position"] == 4


def test_rq09_rewind_after_a_jump_goes_to_the_ticket_before_it(room):
    room.jump("SHOP-142")
    room.rewind()

    assert room.snapshot_for("p1")["ticket"]["key"] == "SHOP-139"


def test_rq10_jump_to_a_key_not_in_the_queue_is_rejected(room):
    room.vote("p1", "5")
    for key in ["SHOP-999", "SHOP-131", None, 42]:  # SHOP-131 is already estimated
        with pytest.raises(CommandError):
            room.jump(key)

    assert room.queue.current.key == "SHOP-134"
    assert room.snapshot_for("p1")["you"]["vote"] == "5"


def test_jump_back_to_an_earlier_ticket_keeps_its_result(room):
    room.vote("p1", "5")
    room.reveal()
    room.confirm(5)
    room.jump("SHOP-134")

    snap = room.snapshot_for("p1")
    assert snap["ticket"]["result"] == {"status": "estimated", "points": 5}
    assert snap["counters"]["session"] == {"tickets": 1, "points": 5}


def test_up_next_lists_five_tickets(room):
    up_next = room.snapshot_for("p1")["up_next"]

    assert [t["key"] for t in up_next] == QUEUE[1:6]


# Auto-reveal


def test_rv03_auto_reveal_off_keeps_cards_face_down(room):
    for pid in ("p1", "p2", "p3"):
        room.vote(pid, "5")

    assert room.round.state == VOTING
    assert room.snapshot_for("p1")["auto_reveal"] is False


def test_auto_reveal_waits_for_everyone_at_the_table(room):
    room.set_auto_reveal(True)
    room.vote("p1", "5")
    room.vote("p2", "8")
    assert room.round.state == VOTING

    room.vote("p3", "3")

    assert room.round.state == REVEALED
    assert room.snapshot_for("p1")["round"]["results"]["votes"] == 3


def test_rv02_away_players_do_not_hold_up_auto_reveal(room):
    room.set_auto_reveal(True)
    room.set_connected("p3", False)
    room.vote("p1", "5")
    assert room.round.state == VOTING

    room.vote("p2", "5")

    assert room.round.state == REVEALED


def test_auto_reveal_fires_when_the_last_holdout_leaves(room):
    room.set_auto_reveal(True)
    room.vote("p1", "5")
    room.vote("p2", "5")

    room.set_connected("p3", False)

    assert room.round.state == REVEALED


def test_rv06_switching_auto_reveal_on_after_everyone_voted_reveals_at_once(room):
    for pid in ("p1", "p2", "p3"):
        room.vote(pid, "5")

    room.set_auto_reveal(True)

    assert room.round.state == REVEALED


def test_auto_reveal_needs_a_vote_and_a_ticket(room):
    room.set_auto_reveal(True)
    for pid in ("p1", "p2", "p3"):
        room.set_connected(pid, False)
    assert room.round.state == VOTING  # nobody connected, no votes

    for _ in QUEUE:
        room.skip()
    room.set_connected("p1", True)
    room.set_auto_reveal(True)
    assert room.round.state == VOTING


def test_auto_reveal_is_on_or_off(room):
    with pytest.raises(CommandError):
        room.set_auto_reveal("yes")


def test_auto_reveal_starts_from_the_room_setting(fake_backlog, clock):
    room = Room(fake_backlog, clock=clock, auto_reveal=True)
    room.join("p1", "Ana")
    room.vote("p1", "5")

    assert room.round.state == REVEALED


# Sitting out


def test_so01_sitting_out_leaves_the_table_and_drops_the_vote(room):
    room.vote("p2", "8")

    room.sit_out("p2")

    snap = room.snapshot_for("p2")
    assert table(room) == ["Ana", "Cy"]
    assert watchers(room) == ["Ben"]
    assert snap["you"]["sitting_out"] is True
    assert snap["you"]["seated"] is True  # still in the room, and sees everything
    assert snap["you"]["vote"] is None
    assert "p2" not in room.round.votes
    assert snap["ticket"]["key"] == "SHOP-134"


def test_so02_voting_while_sitting_out_is_rejected(room):
    room.sit_out("p2")

    with pytest.raises(CommandError) as err:
        room.vote("p2", "5")
    assert err.value.code == "sitting_out"


def test_so03_join_the_table_again(room):
    room.sit_out("p2")
    room.sit_in("p2")

    room.vote("p2", "5")
    assert table(room) == ["Ana", "Ben", "Cy"]
    assert watchers(room) == []
    assert room.snapshot_for("p2")["you"]["sitting_out"] is False


def test_so04_sitting_out_survives_a_reset(room, clock):
    room.sit_out("p2")
    room.reset()
    room.check_in("p1", "Ana")
    room.check_in("p2", "Ben")

    assert table(room) == ["Ana"]
    assert watchers(room) == ["Ben"]


def test_sitting_out_lets_auto_reveal_go_ahead(room):
    room.set_auto_reveal(True)
    room.vote("p1", "5")
    room.vote("p2", "5")

    room.sit_out("p3")

    assert room.round.state == REVEALED


def test_sitting_out_needs_a_seat(room):
    with pytest.raises(CommandError):
        room.sit_out("nobody")


# Removing a player


def test_removing_a_player_drops_the_seat_and_vote(room):
    room.vote("p2", "8")

    room.remove("p2")

    assert table(room) == ["Ana", "Cy"]
    assert "p2" not in room.round.votes
    snap = room.snapshot_for("p2")
    assert snap["you"]["seated"] is False
    assert snap["you"]["removed"] is True


def test_a_removed_player_can_join_again(room):
    room.remove("p2")
    room.join("p2", "Ben")

    snap = room.snapshot_for("p2")
    assert snap["you"]["seated"] is True
    assert snap["you"]["removed"] is False
    room.vote("p2", "5")


def test_removing_a_player_who_sits_out(room):
    room.sit_out("p2")
    room.remove("p2")

    assert watchers(room) == []
    room.join("p2", "Ben")
    assert table(room) == ["Ana", "Cy", "Ben"]  # back at the table, not watching


def test_removing_the_last_holdout_triggers_auto_reveal(room):
    room.set_auto_reveal(True)
    room.vote("p1", "5")
    room.vote("p2", "5")

    room.remove("p3")

    assert room.round.state == REVEALED


def test_removing_an_unknown_player_is_rejected(room):
    with pytest.raises(CommandError):
        room.remove("nobody")


# Leaving the table


def test_um01_leaving_drops_the_seat_and_vote_without_the_removed_notice(room):
    room.vote("p2", "8")
    room.sit_out("p3")

    room.leave("p2")
    room.leave("p3")

    assert table(room) == ["Ana"]
    assert watchers(room) == []
    assert "p2" not in room.round.votes
    snap = room.snapshot_for("p2")
    assert snap["you"]["seated"] is False
    assert snap["you"]["removed"] is False
    room.join("p3", "Cy")
    assert table(room) == ["Ana", "Cy"]  # back at the table, not watching


def test_leaving_lets_auto_reveal_go_ahead(room):
    room.set_auto_reveal(True)
    room.vote("p1", "5")
    room.vote("p2", "5")

    room.leave("p3")

    assert room.round.state == REVEALED


def test_leaving_without_a_seat_does_nothing(room):
    room.leave("nobody")
    room.leave(None)

    assert table(room) == ["Ana", "Ben", "Cy"]


# The session summary


def test_summary_lists_tickets_with_results_in_queue_order(room):
    assert room.summary() == []

    room.vote("p1", "5")
    room.vote("p2", "5")
    room.vote("p3", "8")
    room.reveal()
    room.confirm(5)
    room.skip()  # SHOP-138, never revealed
    room.vote("p1", "?")
    room.reveal()
    room.skip()  # SHOP-139, revealed then skipped

    assert room.summary() == [
        {
            "key": "SHOP-134",
            "summary": "Order confirmation page redesign",
            "status": "estimated",
            "points": 5,
            "average": 6.0,
            "votes": [{"label": "5", "count": 2}, {"label": "8", "count": 1}],
        },
        {
            "key": "SHOP-138",
            "summary": "Address autocomplete at checkout",
            "status": "skipped",
            "points": None,
            "average": None,
            "votes": [],
        },
        {
            "key": "SHOP-139",
            "summary": "Show a delivery estimate on the product page",
            "status": "skipped",
            "points": None,
            "average": None,
            "votes": [{"label": "?", "count": 1}],
        },
    ]


def test_sm03_re_estimating_replaces_the_summary_entry(room):
    room.vote("p1", "5")
    room.reveal()
    room.confirm(5)
    room.rewind()
    room.vote("p1", "8")
    room.vote("p2", "8")
    room.reveal()
    room.confirm(8)

    entries = room.summary()
    assert len(entries) == 1
    assert entries[0]["points"] == 8
    assert entries[0]["votes"] == [{"label": "8", "count": 2}]


def test_summary_has_no_names(room):
    room.vote("p1", "5")
    room.reveal()
    room.confirm(5)

    text = repr(room.summary())
    for name in ("Ana", "Ben", "Cy", "p1", "p2", "p3"):
        assert name not in text
