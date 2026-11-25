"""The menu behind your name in the room header, in a real browser: cases UM-04 to UM-08, UM-11."""

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
    expect(items(menu)).to_have_text(
        ["Your rooms", "Room settings", "Change name", "Tour", "Log out"]
    )

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
    expect(items(menu)).to_have_text(["Your rooms", "Change name", "Tour", "Log out"])

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
    expect(items(menu)).to_have_text(["Change name", "Tour", "Log out"])
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


# Wraps WebSocket so a test can cut the room's connection and keep it from coming back,
# as when a phone wakes up with a dead socket.
CUTTABLE_SOCKETS = """(() => {
  const Real = window.WebSocket;
  window.__sockets = [];
  window.WebSocket = function (url, protocols) {
    const socket = new Real(window.__blocked ? "ws://127.0.0.1:9/" : url, protocols);
    window.__sockets.push(socket);
    return socket;
  };
  window.WebSocket.prototype = Real.prototype;
  Object.assign(window.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
})();"""


def test_um08_logging_out_with_the_connection_down_still_leaves_the_table(table):
    fay = table.join("Fay", facilitator=True)
    context = table.new_context()
    context.add_init_script(CUTTABLE_SOCKETS)
    ana_page = table.open(context)
    ana_page.get_by_label("Your name").fill("Ana")
    ana_page.get_by_role("button", name="Join room").click()
    expect(players(fay.page)).to_have_count(2)
    # Wait for Ana's own first update too, or the cut can land before her page has a room
    # to show, and so before her menu exists.
    expect(ana_page.get_by_role("region", name="Your card")).to_be_visible()

    ana_page.evaluate("window.__blocked = true; window.__sockets.forEach(s => s.close())")
    expect(ana_page.get_by_text("Connection lost. Reconnecting…")).to_be_visible()
    ana_page.get_by_role("banner").get_by_role("button", name="Ana").click()
    ana_page.get_by_role("menuitem", name="Log out").click()

    expect(ana_page.get_by_label("Your name")).to_have_value("")
    expect(players(fay.page)).to_have_count(1)
    expect(fay.page.locator('[data-player="Ana"]')).to_have_count(0)


def test_um11_change_name_keeps_the_seat_and_the_vote(table):
    fay, ana, ben = seat_three(table)
    fay.vote("5")
    expect(ana.page.get_by_label("Fay has voted")).to_be_visible()

    open_menu(fay).get_by_role("menuitem", name="Change name").click()
    form = fay.page.get_by_role("dialog", name="Change name")
    field = form.get_by_label("Name at the table")
    expect(field).to_have_value("Fay")

    # A name another seat holds is refused, and the form stays open to fix it.
    field.fill("ana")
    form.get_by_role("button", name="Save").click()
    expect(form.get_by_role("alert")).to_contain_text("already called Ana")
    expect(form).to_be_visible()

    field.fill("Fiona")
    form.get_by_role("button", name="Save").click()
    expect(form).to_be_hidden()
    expect(fay.page.get_by_role("banner").get_by_role("button", name="Fiona")).to_be_visible()
    expect(ana.page.get_by_label("Fiona has voted")).to_be_visible()  # same seat, vote kept
    expect(players(ana.page)).to_have_count(3)
    expect(fay.page.get_by_text("Facilitator controls")).to_be_visible()

    # The browser remembers the new name.
    fay.page.reload()
    expect(fay.page.get_by_role("banner").get_by_role("button", name="Fiona")).to_be_visible()
