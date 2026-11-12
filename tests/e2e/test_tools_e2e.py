"""Session tools in a real browser: cases RR-09, RQ-11, SO-05, RP-02 and SM-04."""

import csv
import io

from playwright.sync_api import expect

from tests.e2e.conftest import players
from tests.e2e.test_room_e2e import seat_three, vote_and_reveal


def test_rr09_reveal_shows_the_spread_and_marks_highest_and_lowest(table):
    fay, ana, ben = seat_three(table)

    vote_and_reveal(fay, ana, ben, ("3", "5", "8"))

    for seat in (fay, ana, ben):
        page = seat.page
        spread = page.get_by_role("list", name="Vote spread")
        for label in ("3", "5", "8"):
            expect(spread.get_by_label(f"{label}: 1 vote")).to_be_visible()
        expect(page.locator('[data-player="Ben"]')).to_contain_text("Highest")
        expect(page.locator('[data-player="Fay"]')).to_contain_text("Lowest")
        expect(page.locator('[data-player="Ana"]')).not_to_contain_text("Highest")


def test_rq11_choosing_a_ticket_in_up_next_moves_every_screen(table):
    fay, ana, ben = seat_three(table)
    up_next = fay.page.get_by_role("complementary", name="Facilitator panel")

    up_next.get_by_role("button", name="Go to SHOP-142").click()

    for seat in (fay, ana, ben):
        region = seat.page.get_by_role("region", name="Current ticket")
        expect(region.get_by_text("SHOP-142", exact=True)).to_be_visible()
        expect(seat.page.get_by_text("Ticket 4 of 8")).to_be_visible()


def test_so05_facilitator_sits_out_and_still_runs_the_round(table):
    fay, ana, ben = seat_three(table)

    fay.press("Sit out")

    for seat in (fay, ana, ben):
        expect(seat.page.get_by_text("Watching: Fay")).to_be_visible()
        expect(players(seat.page)).to_have_count(2)
    expect(fay.page.get_by_role("region", name="Your card")).to_contain_text("You are watching")
    ana.vote("5")
    ben.vote("8")
    expect(fay.page.get_by_text("2 of 2 voted")).to_be_visible()
    fay.press("Reveal cards")
    expect(ana.page.get_by_label("Ben played 8")).to_be_visible()

    fay.press("Join the table")
    expect(players(ana.page)).to_have_count(3)


def test_rp02_removed_player_is_told_and_can_join_again(table):
    fay, ana, ben = seat_three(table)
    ben.vote("8")
    expect(fay.page.get_by_text("1 of 3 voted")).to_be_visible()

    fay.page.get_by_role("button", name="Remove Ben").click()

    expect(players(fay.page)).to_have_count(2)
    expect(fay.page.get_by_text("0 of 2 voted")).to_be_visible()
    expect(ben.page.get_by_text("A facilitator removed you from the table.")).to_be_visible()
    ben.press("Join again")
    expect(players(fay.page)).to_have_count(3)
    expect(ben.page.get_by_role("region", name="Your card")).to_be_visible()


def test_sm04_copy_and_download_the_session_summary(table):
    table.owner.grant_permissions(["clipboard-read", "clipboard-write"], origin=table.base)
    fay, ana, ben = seat_three(table)
    vote_and_reveal(fay, ana, ben, ("5", "5", "8"))
    fay.press("Confirm 5 points")
    expect(fay.page.get_by_text("SHOP-138", exact=True).first).to_be_visible()
    fay.press("Skip")

    panel = fay.page.get_by_role("region", name="Session summary")
    expect(panel).to_contain_text("1 estimated · 1 skipped")
    panel.get_by_role("button", name="Copy summary").click()
    expect(panel.get_by_role("button", name="Copied")).to_be_visible()
    text = fay.page.evaluate("navigator.clipboard.readText()")
    assert "SHOP-134 Order confirmation page redesign: 5 points" in text
    assert "votes 5×2, 8×1" in text
    assert "SHOP-138 Address autocomplete at checkout: skipped" in text
    assert "1 ticket · 5 points" in text

    with fay.page.expect_download() as download:
        panel.get_by_role("button", name="Download CSV").click()
    assert download.value.suggested_filename.startswith(f"scrum-poker-{table.slug}-")
    rows = list(csv.DictReader(io.StringIO(open(download.value.path()).read())))
    assert [(r["key"], r["status"], r["points"]) for r in rows] == [
        ("SHOP-134", "estimated", "5"),
        ("SHOP-138", "skipped", ""),
    ]
    assert rows[0]["votes"] == "5×2, 8×1"
    assert rows[0]["average"] == "6.0"

    # Players get no summary.
    expect(ana.page.get_by_role("region", name="Session summary")).to_have_count(0)
