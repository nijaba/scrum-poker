"""Phones, Remote view and dark mode in a real browser.

Cases PH-01 to PH-05, RV-01 to RV-03, TH-01 and TH-02.
"""

import re

from playwright.sync_api import expect

from tests.e2e.conftest import players
from tests.e2e.test_room_e2e import seat_three

PHONE = {"width": 440, "height": 956}
LIGHT_GROUND = "rgb(242, 244, 243)"
DARK_GROUND = "rgb(14, 19, 17)"


def as_phone(seat):
    seat.page.set_viewport_size(PHONE)
    expect(seat.page.locator(".dock")).to_be_visible()
    return seat


def in_view(locator):
    box = locator.bounding_box()
    assert box is not None, "not on screen"
    assert box["y"] >= 0 and box["y"] + box["height"] <= PHONE["height"] + 0.5, box


def open_menu(seat):
    page = seat.page
    page.get_by_role("banner").get_by_role("button", name=seat.name).click()
    return page.get_by_role("menu")


def ground(page):
    return page.evaluate("getComputedStyle(document.body).backgroundColor")


def test_ph01_a_player_sees_ticket_table_and_hand_without_scrolling(table):
    fay, ana, ben = seat_three(table)
    as_phone(ana)
    page = ana.page

    header = page.get_by_role("banner").bounding_box()
    assert header and header["height"] <= 64
    in_view(page.get_by_role("heading", level=1))
    in_view(page.get_by_role("region", name="Players"))
    hand = page.get_by_role("region", name="Your card")
    for button in hand.get_by_role("button").all():
        in_view(button)

    # The hand is docked: at the foot of the screen however far the page scrolls.
    page.mouse.wheel(0, 2000)
    in_view(hand)
    ana.vote("5")
    expect(fay.page.get_by_label("Ana has voted")).to_be_visible()


def test_ph02_a_facilitator_reveals_and_confirms_from_the_dock(table):
    fay, ana, ben = seat_three(table)
    as_phone(fay)
    page = fay.page
    first = page.get_by_role("heading", level=1).inner_text()

    for seat, card in ((fay, "5"), (ana, "5"), (ben, "8")):
        seat.vote(card)
    dock = page.locator(".dock")
    reveal = dock.get_by_role("button", name=re.compile(r"^Reveal cards · 3 of 3$"))
    expect(reveal).to_be_visible()
    in_view(reveal)
    reveal.click()

    final = page.get_by_role("region", name="Final points")
    expect(final).to_be_visible()
    confirm = final.get_by_role("button", name="Confirm 5 points")
    in_view(confirm)
    confirm.click()

    expect(page.get_by_role("heading", level=1)).not_to_have_text(first)
    expect(ana.page.get_by_role("heading", level=1)).not_to_have_text(first)
    menu = open_menu(fay)
    expect(menu).to_contain_text("Session: 1 ticket · 5 points")


def test_ph03_the_more_controls_sheet_opens_and_closes(table):
    fay, ana, ben = seat_three(table)
    as_phone(fay)
    page = fay.page

    page.get_by_role("button", name="More controls").click()
    sheet = page.get_by_role("dialog", name="Session controls")
    expect(sheet).to_be_visible()
    expect(sheet.get_by_role("region", name="Countdown")).to_be_visible()
    expect(sheet.get_by_role("button", name="Skip", exact=True)).to_be_visible()
    expect(sheet.get_by_role("region", name="Session summary")).to_be_visible()
    # Reveal lives in the dock, not twice.
    expect(sheet.get_by_role("button", name="Reveal cards")).to_have_count(0)

    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()

    page.get_by_role("button", name="More controls").click()
    sheet.get_by_role("button", name="Skip", exact=True).click()
    sheet.get_by_role("button", name="Close").click()
    expect(sheet).to_be_hidden()
    expect(fay.page.get_by_role("banner").get_by_text("Ticket 2 of")).to_be_visible()


def test_ph04_the_phone_menu_holds_counters_mute_and_theme(table):
    fay, ana, ben = seat_three(table)
    fay.page.get_by_role("button", name="Sound off").click()  # turn the room's sound on
    expect(fay.page.get_by_role("button", name="Sound on")).to_be_visible()
    as_phone(fay)

    menu = open_menu(fay)
    expect(menu).to_contain_text("Session: 0 tickets · 0 points")
    expect(menu).to_contain_text("Backlog:")
    mute = menu.get_by_role("menuitemcheckbox", name="Mute")
    expect(mute).to_have_attribute("aria-checked", "false")
    mute.click()
    expect(mute).to_have_attribute("aria-checked", "true")
    expect(menu.get_by_role("menuitemradio")).to_have_text(["System", "Light", "Dark"])
    expect(fay.page.get_by_role("button", name="Mini mode")).to_have_count(0)


def test_ph05_a_wide_window_keeps_the_desktop_layout(table):
    fay, ana, ben = seat_three(table)
    page = fay.page
    page.set_viewport_size({"width": 1280, "height": 800})

    expect(page.locator(".dock")).to_have_count(0)
    expect(page.get_by_role("button", name="Mini mode")).to_be_visible()
    expect(page.get_by_label("Session counter")).to_be_visible()
    panel = page.get_by_role("complementary", name="Facilitator panel")
    tablebox = page.get_by_role("region", name="Players").bounding_box()
    panelbox = panel.bounding_box()
    assert panelbox and tablebox and panelbox["x"] > tablebox["x"] + tablebox["width"] - 1
    expect(panel.get_by_role("button", name="Reveal cards")).to_be_visible()


def test_rv01_a_player_votes_from_remote_view_and_it_sticks(table):
    fay, ana, ben = seat_three(table)
    as_phone(ana)
    page = ana.page

    item = open_menu(ana).get_by_role("menuitemcheckbox", name="Remote view")
    expect(item).to_have_attribute("aria-checked", "false")
    item.click()
    remote = page.get_by_role("region", name="Remote view")
    expect(remote).to_be_visible()
    remote.get_by_role("button", name="5", exact=True).click()
    expect(remote.get_by_text("You played 5.")).to_be_visible()
    expect(fay.page.get_by_label("Ana has voted")).to_be_visible()

    page.reload()
    expect(page.get_by_role("region", name="Remote view")).to_be_visible()
    page.get_by_role("button", name="Full room").click()
    expect(page.get_by_role("region", name="Remote view")).to_have_count(0)
    expect(page.get_by_role("region", name="Your card")).to_be_visible()
    expect(players(page)).to_have_count(3)


def test_rv02_remote_view_shows_the_result_after_reveal(table):
    fay, ana, ben = seat_three(table)
    as_phone(ana)
    open_menu(ana).get_by_role("menuitemcheckbox", name="Remote view").click()
    remote = ana.page.get_by_role("region", name="Remote view")
    remote.get_by_role("button", name="3", exact=True).click()
    fay.vote("5")
    ben.vote("5")
    expect(fay.page.get_by_text("3 of 3 voted")).to_be_visible()
    fay.press("Reveal cards")

    expect(remote.get_by_label("Your card: 3")).to_be_visible()
    expect(remote.get_by_label("Most chosen: 5")).to_be_visible()
    expect(remote.locator('[data-figure="average"]')).to_have_text("4.3")
    expect(remote.locator('[data-figure="median"]')).to_have_text("5")
    expect(remote.get_by_text("You played the lowest card.")).to_be_visible()


def test_rv03_facilitators_are_not_offered_remote_view(table):
    fay, ana, ben = seat_three(table)
    as_phone(fay)
    menu = open_menu(fay)
    expect(menu.get_by_role("menuitemradio", name="System")).to_be_visible()
    expect(menu.get_by_role("menuitemcheckbox", name="Remote view")).to_have_count(0)


def test_th01_pages_follow_the_device_theme(browser, server, table):
    for scheme, colour in (("dark", DARK_GROUND), ("light", LIGHT_GROUND)):
        context = browser.new_context(color_scheme=scheme)
        page = context.new_page()
        page.goto(server)
        expect(page.get_by_role("heading", name="Run a session")).to_be_visible()
        assert ground(page) == colour
        page.goto(table.url)
        expect(page.get_by_label("Your name")).to_be_visible()
        assert ground(page) == colour
        context.close()


def test_th02_the_theme_choice_overrides_the_device_and_is_kept(browser, server, table):
    fay = table.join("Fay", facilitator=True)
    page = fay.page
    page.emulate_media(color_scheme="light")
    assert ground(page) == LIGHT_GROUND

    open_menu(fay).get_by_role("menuitemradio", name="Dark").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    assert ground(page) == DARK_GROUND
    page.reload()
    expect(players(page)).to_have_count(1)
    assert ground(page) == DARK_GROUND

    theme = page.get_by_label("Theme")
    expect(theme).to_have_value("dark")
    theme.select_option("light")
    assert ground(page) == LIGHT_GROUND
    page.emulate_media(color_scheme="dark")
    assert ground(page) == LIGHT_GROUND  # the choice beats the device
    theme.select_option("system")
    expect(page.locator("html")).not_to_have_attribute("data-theme", re.compile("."))
    assert ground(page) == DARK_GROUND
    page.reload()
    expect(players(page)).to_have_count(1)
    assert ground(page) == DARK_GROUND
