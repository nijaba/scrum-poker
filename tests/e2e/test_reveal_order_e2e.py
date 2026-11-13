"""The table sorts the cards on reveal: cases RR-10 and RR-11."""

import re

from playwright.sync_api import expect

from tests.e2e.conftest import players

JOIN_ORDER = ["Fay", "Ana", "Ben", "Cid"]
# Scale order: Ana's 3, then Fay's 8, then Ben's "?", and Cid, who did not vote, last.
SORTED = ["Ana", "Fay", "Ben", "Cid"]


def names(order):
    return [re.compile(rf"\b{name}\b") for name in order]


def seat_four_and_reveal(table, before_reveal=None):
    fay = table.join("Fay", facilitator=True)
    ana = table.join("Ana")
    ben = table.join("Ben")
    cid = table.join("Cid")
    everyone = (fay, ana, ben, cid)
    for seat in everyone:
        expect(players(seat.page)).to_have_text(names(JOIN_ORDER))
    if before_reveal:
        before_reveal(everyone)
    fay.vote("8")
    ana.vote("3")
    ben.vote("?")
    for seat in everyone:
        expect(seat.page.get_by_text("3 of 4 voted")).to_be_visible()
    fay.press("Reveal cards")
    return everyone


def test_rr10_reveal_sorts_the_cards_in_scale_order_on_every_screen(table):
    everyone = seat_four_and_reveal(table)
    fay = everyone[0]

    for seat in everyone:
        expect(seat.page.get_by_text("Cards revealed")).to_be_visible()
        expect(players(seat.page)).to_have_text(names(SORTED))

    fay.press("Restart vote")
    for seat in everyone:
        expect(seat.page.get_by_text("Voting open")).to_be_visible()
        expect(players(seat.page)).to_have_text(names(JOIN_ORDER))


def test_rr11_reduced_motion_turns_and_sorts_the_cards_at_once(table):
    def reduce_motion(everyone):
        for seat in everyone:
            seat.page.emulate_media(reduced_motion="reduce")

    everyone = seat_four_and_reveal(table, before_reveal=reduce_motion)

    for seat in everyone:
        page = seat.page
        expect(page.get_by_text("Cards revealed")).to_be_visible()
        # Without the animations there is nothing to wait for: the order is final at once.
        expect(players(page)).to_have_text(names(SORTED), timeout=300)
        durations = page.locator(".flip-inner").evaluate_all(
            "els => els.map(e => getComputedStyle(e).transitionDuration)"
        )
        assert durations and set(durations) == {"0s"}
