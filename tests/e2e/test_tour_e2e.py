"""The tour of the room and of the settings page. Cases TR-01 to TR-06 and TR-08 to TR-10."""

import re

from playwright.sync_api import expect

from tests.e2e.conftest import players
from tests.e2e.test_phone_e2e import PHONE, as_phone, in_view, open_menu
from tests.e2e.test_room_e2e import seat_three

PLAYER_STEPS = ["The ticket", "The table", "Your cards", "The reveal", "Your menu"]
FACILITATOR_STEPS = [
    "The ticket",
    "The table",
    "Your cards",
    "The reveal",
    "Reveal cards",
    "Final points and Confirm",
    "The countdown",
    "Up next and summary",
    "Your menu",
]
PHONE_FACILITATOR_STEPS = [
    "The ticket",
    "The table",
    "Your cards",
    "The reveal",
    "Reveal cards",
    "Final points and Confirm",
    "More controls",
    "Your menu",
]
SETTINGS_STEPS = [
    "Room link",
    "Jira",
    "Queue filter",
    "Scale",
    "Countdown, sound and reveal",
    "Delegates",
]
PLAYER_MORE = ["The counters", "Copy link", "Mini mode", "Who has voted", "Reading the reveal"]
FACILITATOR_MORE = PLAYER_MORE + [
    "Restart, Skip and Rewind",
    "Reset room and Reload backlog",
    "Removing a player",
    "Auto-reveal and sound",
    "The session summary",
    "Room settings",
]
TARGETS = {
    "The ticket": "ticket",
    "The table": "table",
    "Your cards": "hand",
    "Reveal cards": "reveal",
    "The countdown": "countdown",
    "Up next and summary": "summary",
    "More controls": "more",
    "Your menu": "menu",
    "The counters": "counters",
    "Copy link": "copy-link",
    "Mini mode": "mini",
    "Who has voted": "table",
    "Reading the reveal": "table",
    "Restart, Skip and Rewind": "round",
    "Reset room and Reload backlog": "round",
    "Removing a player": "table",
    "Auto-reveal and sound": "auto-reveal",
    "The session summary": "summary",
    "Room settings": "menu",
}


def offer(page):
    return page.get_by_role("region", name="Tour offer")


def caption(page):
    return page.get_by_role("dialog", name=re.compile("."), include_hidden=False).filter(
        has=page.locator(".tour-count")
    )


def outlined(page, target):
    """The outline sits on the part of the page the step explains."""
    spot = page.locator(".tour-spot").bounding_box()
    part = page.locator(f'[data-tour="{target}"]:visible').first.bounding_box()
    assert spot and part, (spot, part)
    for key in ("x", "y", "width", "height"):
        assert abs(spot[key] - part[key]) <= 14, (target, key, spot, part)


def walk(page, titles, phone=False):
    """Step through the tour with Next, checking each title, count and outline; then Done."""
    for i, title in enumerate(titles):
        step = caption(page)
        expect(step.get_by_role("heading")).to_have_text(title)
        expect(step.locator(".tour-count")).to_have_text(f"Step {i + 1} of {len(titles)}")
        if title in TARGETS:
            outlined(page, TARGETS[title])
            if phone:
                in_view(page.locator(".tour-spot"))
                in_view(step)
        if i < len(titles) - 1:
            step.get_by_role("button", name="Next").click()
    caption(page).get_by_role("button", name="Done").click()
    expect(page.locator(".tour-caption")).to_have_count(0)


def test_tr01_the_offer_shows_once_and_no_thanks_keeps_it_away(fresh_table):
    ana = fresh_table.join("Ana")
    page = ana.page
    note = offer(page)
    expect(note).to_be_visible()
    expect(note.get_by_role("button", name="Take the tour")).to_be_visible()
    note.get_by_role("button", name="No thanks").click()
    expect(note).to_have_count(0)
    expect(page.locator(".tour-caption")).to_have_count(0)

    page.reload()
    expect(players(page)).to_have_count(1)
    expect(offer(page)).to_have_count(0)
    # On demand it is still there.
    expect(page.get_by_role("contentinfo").get_by_role("button", name="Tour")).to_be_visible()


def test_tr02_a_player_takes_the_tour_from_the_offer(fresh_table):
    ana = fresh_table.join("Ana")
    page = ana.page
    offer(page).get_by_role("button", name="Take the tour").click()
    expect(offer(page)).to_have_count(0)

    step = caption(page)
    expect(step.get_by_role("heading")).to_have_text("The ticket")
    expect(step.get_by_role("button", name="Back")).to_be_disabled()
    step.get_by_role("button", name="Next").click()
    expect(step.get_by_role("heading")).to_have_text("The table")
    step.get_by_role("button", name="Back").click()
    expect(step.get_by_role("heading")).to_have_text("The ticket")
    walk(page, PLAYER_STEPS)

    page.reload()
    expect(players(page)).to_have_count(1)
    expect(offer(page)).to_have_count(0)


def test_tr03_a_facilitator_tour_adds_the_controls(table):
    fay, ana, ben = seat_three(table)
    page = fay.page
    menu = open_menu(fay)
    menu.get_by_role("menuitem", name="Tour").click()
    expect(caption(page).get_by_role("heading")).to_have_text("The ticket")

    for _ in range(len(FACILITATOR_STEPS) - 1):
        caption(page).get_by_role("button", name="Next").click()
    last = caption(page)
    expect(last.get_by_role("heading")).to_have_text("Your menu")
    expect(last).to_contain_text("Room settings")  # Fay owns the room
    last.get_by_role("button", name="Done").click()

    page.get_by_role("contentinfo").get_by_role("button", name="Tour").click()
    walk(page, FACILITATOR_STEPS)
    # The player's tour has no facilitator steps.
    ana.page.get_by_role("contentinfo").get_by_role("button", name="Tour").click()
    walk(ana.page, PLAYER_STEPS)

    # Once the cards are revealed, the final points step outlines the final points.
    fay.press("Reveal cards")
    expect(page.get_by_role("region", name="Final points")).to_be_visible()
    page.get_by_role("contentinfo").get_by_role("button", name="Tour").click()
    for _ in range(FACILITATOR_STEPS.index("Final points and Confirm")):
        caption(page).get_by_role("button", name="Next").click()
    expect(caption(page).get_by_role("heading")).to_have_text("Final points and Confirm")
    outlined(page, "final")


def test_tr04_a_facilitator_on_a_phone_tours_the_dock(table):
    fay, ana, ben = seat_three(table)
    as_phone(fay)
    page = fay.page
    open_menu(fay).get_by_role("menuitem", name="Tour").click()
    walk(page, PHONE_FACILITATOR_STEPS, phone=True)
    assert page.viewport_size == PHONE


def test_tr05_escape_ends_the_tour_and_the_footer_starts_it_again(fresh_table):
    ana = fresh_table.join("Ana")
    page = ana.page
    offer(page).get_by_role("button", name="No thanks").click()
    start = page.get_by_role("contentinfo").get_by_role("button", name="Tour")
    start.click()
    step = caption(page)
    step.get_by_role("button", name="Next").click()
    expect(step.locator(".tour-count")).to_have_text("Step 2 of 5")

    page.keyboard.press("Escape")
    expect(page.locator(".tour-caption")).to_have_count(0)
    expect(page.locator(".tour-spot")).to_have_count(0)
    expect(start).to_be_focused()

    start.click()
    expect(caption(page).locator(".tour-count")).to_have_text("Step 1 of 5")
    caption(page).get_by_role("button", name="Close").click()
    expect(page.locator(".tour-caption")).to_have_count(0)


def test_tr06_the_owner_tours_the_settings_page(fresh_table):
    page = fresh_table.owner.new_page()
    page.goto(f"{fresh_table.url}/settings")
    note = offer(page)
    expect(note).to_be_visible()
    note.get_by_role("button", name="Take the tour").click()
    walk_settings(page)

    page.reload()
    expect(page.get_by_role("region", name="Delegates")).to_be_visible()
    expect(offer(page)).to_have_count(0)
    page.get_by_role("contentinfo").get_by_role("button", name="Tour").click()
    expect(caption(page).get_by_role("heading")).to_have_text("Room link")


def walk_settings(page):
    for i, title in enumerate(SETTINGS_STEPS):
        step = caption(page)
        expect(step.get_by_role("heading")).to_have_text(title)
        expect(step.locator(".tour-count")).to_have_text(f"Step {i + 1} of {len(SETTINGS_STEPS)}")
        spot = page.locator(".tour-spot").bounding_box()
        part = page.get_by_role("region", name=title).bounding_box()
        assert spot and part and abs(spot["y"] - part["y"]) <= 14, (title, spot, part)
        step.get_by_role("button", name="Done" if i == len(SETTINGS_STEPS) - 1 else "Next").click()
    expect(page.locator(".tour-caption")).to_have_count(0)


def walk_more(page, first, more):
    """Go through the first part, choose Show me more, and walk the second part to Done."""
    total = len(first) + len(more)
    for _ in range(len(first) - 1):
        caption(page).get_by_role("button", name="Next").click()
    step = caption(page)
    expect(step.get_by_role("heading")).to_have_text(first[-1])
    expect(step.locator(".tour-count")).to_have_text(f"Step {len(first)} of {len(first)}")
    expect(step.get_by_role("button", name="Done")).to_be_visible()
    step.get_by_role("button", name="Show me more").click()
    for i, title in enumerate(more, start=len(first)):
        step = caption(page)
        expect(step.get_by_role("heading")).to_have_text(title)
        expect(step.locator(".tour-count")).to_have_text(f"Step {i + 1} of {total}")
        outlined(page, TARGETS[title])
        if i < total - 1:
            step.get_by_role("button", name="Next").click()
    expect(caption(page).get_by_role("button", name="Show me more")).to_have_count(0)
    caption(page).get_by_role("button", name="Done").click()
    expect(page.locator(".tour-caption")).to_have_count(0)


def test_tr08_a_player_asks_for_more(fresh_table):
    ana = fresh_table.join("Ana")
    page = ana.page
    offer(page).get_by_role("button", name="Take the tour").click()
    walk_more(page, PLAYER_STEPS, PLAYER_MORE)
    # The second part says what the table and the reveal mean.
    page.get_by_role("contentinfo").get_by_role("button", name="Tour").click()
    for _ in range(len(PLAYER_STEPS) - 1):
        caption(page).get_by_role("button", name="Next").click()
    caption(page).get_by_role("button", name="Show me more").click()
    for _ in range(PLAYER_MORE.index("Who has voted")):
        caption(page).get_by_role("button", name="Next").click()
    expect(caption(page)).to_contain_text("Away")
    caption(page).get_by_role("button", name="Next").click()
    expect(caption(page)).to_contain_text("Highest")


def test_tr09_a_facilitator_asks_for_more(table):
    fay, ana, ben = seat_three(table)
    page = fay.page
    open_menu(fay).get_by_role("menuitem", name="Tour").click()
    walk_more(page, FACILITATOR_STEPS, FACILITATOR_MORE)
    # A player's second part has no facilitator steps.
    ana.page.get_by_role("contentinfo").get_by_role("button", name="Tour").click()
    walk_more(ana.page, PLAYER_STEPS, PLAYER_MORE)


def test_tr10_the_settings_tour_of_a_new_room_starts_with_the_checklist(browser, server):
    from tests.e2e.conftest import sign_in

    page = browser.new_page()
    sign_in(page, server, "Olive Owner")
    page.get_by_label("Short name").fill("e2e-tour-new")
    page.get_by_role("button", name="Create room").click()
    page.wait_for_url(f"{server}/r/e2e-tour-new/settings")
    offer(page).get_by_role("button", name="Take the tour").click()
    titles = ["Getting started", *SETTINGS_STEPS]
    for i, title in enumerate(titles):
        step = caption(page)
        expect(step.get_by_role("heading")).to_have_text(title)
        expect(step.locator(".tour-count")).to_have_text(f"Step {i + 1} of {len(titles)}")
        region = "Get this room ready" if title == "Getting started" else title
        spot = page.locator(".tour-spot").bounding_box()
        part = page.get_by_role("region", name=region).bounding_box()
        assert spot and part and abs(spot["y"] - part["y"]) <= 14, (title, spot, part)
        if title == "Delegates":
            expect(step).to_contain_text("Make owner")
        step.get_by_role("button", name="Done" if i == len(titles) - 1 else "Next").click()
    page.close()
