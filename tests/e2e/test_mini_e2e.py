"""Mini mode in a real browser: cases MM-02, MM-03 and MM-04.

The always-on-top Picture-in-Picture window cannot be driven by Playwright, so
these tests remove the API before the page loads. The button then opens the
popup fallback, which renders the same view (see docs/test-plan.md, Mini mode).
"""

import re

from playwright.sync_api import Page, expect

from tests.e2e.conftest import Seat, Table

NO_PIP = "delete window.documentPictureInPicture;"


def open_mini(seat: Seat) -> Page:
    with seat.page.expect_popup() as popup:
        seat.press("Mini mode")
    mini = popup.value
    expect(mini.get_by_role("region", name="Mini room")).to_be_visible()
    return mini


def seat_with_mini(table: Table) -> tuple[Seat, Seat, Page]:
    table.owner.add_init_script(NO_PIP)
    fay = table.join("Fay", facilitator=True)
    context = table.new_context()
    context.add_init_script(NO_PIP)
    page = table.open(context)
    page.get_by_label("Your name").fill("Ana")
    page.get_by_role("button", name="Join room").click()
    ana = Seat("Ana", context, page)
    expect(page.get_by_text("0 of 2 voted")).to_be_visible()
    return fay, ana, open_mini(ana)


def mini_card(mini: Page, label: str):
    return mini.get_by_role("group", name="Cards").get_by_role(
        "button", name="Not sure" if label == "?" else label, exact=True
    )


def test_mm02_mini_view_shows_key_countdown_cards_and_voted_count(table):
    fay, ana, mini = seat_with_mini(table)

    view = mini.get_by_role("region", name="Mini room")
    expect(view.get_by_text("SHOP-134", exact=True)).to_be_visible()
    expect(view.get_by_text("Order confirmation page redesign")).to_be_visible()
    expect(view.get_by_label("Countdown")).to_have_text(re.compile(r"\d:\d\d"))
    for label in ["1", "2", "3", "5", "8", "13", "21", "?"]:
        expect(mini_card(mini, label)).to_be_visible()
    expect(view.get_by_text("0 of 2 voted")).to_be_visible()

    # The countdown runs in the mini view too.
    fay.press("Start")
    expect(view.get_by_label("Countdown")).to_have_text(re.compile(r"0:(2\d|30)"))
    mini.wait_for_timeout(1_500)
    expect(view.get_by_label("Countdown")).not_to_have_text("0:30")

    # The mini window carries the app's icon.
    expect(mini.locator('link[rel="icon"][type="image/svg+xml"]')).to_have_count(1)

    # The view fits the mock-up's 340 by 256 window without scrolling.
    size = mini.evaluate(
        "() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight,"
        " innerWidth, innerHeight]"
    )
    assert size[0] <= size[2] and size[1] <= size[3], size


def test_mm03_vote_from_the_mini_view_registers_everywhere(table):
    fay, ana, mini = seat_with_mini(table)

    mini_card(mini, "8").click()

    expect(mini_card(mini, "8")).to_have_attribute("aria-pressed", "true")
    expect(mini.get_by_text("You voted 8")).to_be_visible()
    expect(mini.get_by_text("1 of 2 voted")).to_be_visible()
    expect(ana.card("8")).to_have_attribute("aria-pressed", "true")
    expect(fay.page.get_by_text("1 of 2 voted")).to_be_visible()

    fay.vote("5")
    fay.press("Reveal cards")
    expect(fay.page.get_by_label("Ana played 8")).to_be_visible()
    expect(mini.get_by_text("Cards revealed")).to_be_visible()


def test_mm04_mini_view_follows_the_facilitator_to_the_next_ticket(table):
    fay, ana, mini = seat_with_mini(table)
    view = mini.get_by_role("region", name="Mini room")
    mini_card(mini, "3").click()
    expect(view.get_by_text("You voted 3")).to_be_visible()

    fay.press("Skip")

    expect(view.get_by_text("SHOP-138", exact=True)).to_be_visible()
    expect(view.get_by_text("SHOP-134", exact=True)).to_have_count(0)
    expect(view.get_by_text("0 of 2 voted")).to_be_visible()
    expect(mini_card(mini, "3")).to_have_attribute("aria-pressed", "false")


def test_mini_mode_button_reuses_the_open_window(table):
    fay, ana, mini = seat_with_mini(table)
    pages = len(ana.context.pages)

    ana.press("Mini mode")

    ana.page.wait_for_timeout(300)
    assert len(ana.context.pages) == pages
    expect(mini.get_by_role("region", name="Mini room")).to_be_visible()
