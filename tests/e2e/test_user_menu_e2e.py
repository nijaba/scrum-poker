"""The menu behind your name in the room header, in a real browser: cases UM-04 to UM-07."""

from playwright.sync_api import expect

from tests.e2e.conftest import players, sign_in
from tests.e2e.test_room_e2e import seat_three


def open_menu(seat):
    page = seat.page
    button = page.get_by_role("banner").get_by_role("button", name=seat.name)
    button.click()
    expect(button).to_have_attribute("aria-expanded", "true")
    return page.get_by_role("menu")


def items(menu):
    return menu.get_by_role("menuitem")


def test_um04_owner_menu_offers_rooms_settings_and_log_out(table):
    fay, ana, ben = seat_three(table)

    menu = open_menu(fay)
    expect(items(menu)).to_have_text(["Your rooms", "Room settings", "Log out"])

    # Escape closes it and gives focus back to the name.
    fay.page.keyboard.press("Escape")
    expect(menu).to_have_count(0)
    expect(fay.page.get_by_role("banner").get_by_role("button", name="Fay")).to_be_focused()

    open_menu(fay).get_by_role("menuitem", name="Room settings").click()
    fay.page.wait_for_url(f"{table.url}/settings")

    fay.page.goto(table.url)
    open_menu(fay).get_by_role("menuitem", name="Your rooms").click()
    fay.page.wait_for_url(f"{table.base}/")
    expect(fay.page.get_by_role("region", name="Your rooms")).to_be_visible()


def test_um05_signed_in_person_gets_rooms_and_log_out_and_leaves_for_home(table):
    fay = table.join("Fay", facilitator=True)
    context = table.new_context()
    page = context.new_page()
    sign_in(page, table.base, "Cole Colleague", next_path=f"/r/{table.slug}")
    page.get_by_role("button", name="Join room").click()
    expect(players(fay.page)).to_have_count(2)

    cole = type(fay)("Cole Colleague", context, page)
    menu = open_menu(cole)
    expect(items(menu)).to_have_text(["Your rooms", "Log out"])

    menu.get_by_role("menuitem", name="Log out").click()

    page.wait_for_url(f"{table.base}/")
    expect(page.get_by_role("region", name="Sign in")).to_be_visible()
    expect(players(fay.page)).to_have_count(1)
    # The saved name stays: back in the room, they sit down again as a player.
    page.goto(table.url)
    expect(page.get_by_role("region", name="Your card")).to_be_visible()
    expect(page.get_by_role("banner")).to_contain_text("Player")
    expect(players(fay.page)).to_have_count(2)


def test_um06_player_logs_out_and_the_name_is_forgotten(table):
    fay, ana, ben = seat_three(table)
    ben.vote("8")
    expect(fay.page.get_by_text("1 of 3 voted")).to_be_visible()

    menu = open_menu(ben)
    expect(items(menu)).to_have_text(["Log out"])
    menu.get_by_role("menuitem", name="Log out").click()

    expect(ben.page.get_by_label("Your name")).to_have_value("")
    expect(players(fay.page)).to_have_count(2)
    expect(fay.page.get_by_text("0 of 2 voted")).to_be_visible()
    ben.page.reload()
    expect(ben.page.get_by_label("Your name")).to_have_value("")

    # Joining again is a new seat.
    ben.page.get_by_label("Your name").fill("Benjamin")
    ben.page.get_by_role("button", name="Join room").click()
    expect(players(fay.page)).to_have_count(3)
    expect(fay.page.locator('[data-player="Benjamin"]')).to_be_visible()


def test_um07_the_room_name_leads_home_where_a_player_can_sign_in(table):
    fay, ana, ben = seat_three(table)

    home = ben.page.get_by_role("banner").get_by_role("link", name=table.slug, exact=True)
    expect(home).to_have_attribute("href", "/")
    home.click()

    ben.page.wait_for_url(f"{table.base}/")
    expect(ben.page.get_by_role("region", name="Sign in")).to_be_visible()


def test_menu_closes_on_a_click_outside(table):
    fay = table.join("Fay", facilitator=True)
    menu = open_menu(fay)

    fay.page.get_by_role("main").click(position={"x": 5, "y": 5})

    expect(menu).to_have_count(0)
