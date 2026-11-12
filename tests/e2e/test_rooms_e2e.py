"""The step 3 screens in a real browser: the rooms page, room settings and delegate access.

The rules behind them (AR-01 to AR-13) are proved at Integration level; these
check that the pages drive them as a person would.
"""

import re
import sqlite3

from playwright.sync_api import expect

from tests.e2e.conftest import connect_jira, sign_in


def test_owner_creates_and_configures_a_room_and_a_delegate_runs_it(browser, server):
    owner = browser.new_context()
    page = owner.new_page()
    sign_in(page, server, "Olive Owner")

    # Create a room from the rooms page.
    page.get_by_label("Short name").fill("e2e-settings")
    page.get_by_role("button", name="Create room").click()
    page.wait_for_url(f"{server}/r/e2e-settings/settings")

    # Connect Jira and pick the board, through the consent page.
    connect_jira(page, server, "e2e-settings")
    expect(page.get_by_text("Connected as owner@example.com")).to_be_visible()

    # Change the scale, add a delegate and rename the room, then save.
    page.get_by_label("T-shirt").check()
    page.get_by_label("Google email or GitHub username").fill("Delegate@Example.com")
    page.get_by_role("button", name="Add delegate").click()
    expect(page.get_by_text("delegate@example.com")).to_be_visible()
    page.get_by_label("Short name").fill("e2e-renamed")
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_text("Saved.")).to_be_visible()
    expect(page).to_have_url(f"{server}/r/e2e-renamed/settings")

    # The old link redirects; the room uses T-shirt cards.
    page.goto(f"{server}/r/e2e-settings")
    expect(page).to_have_url(f"{server}/r/e2e-renamed")
    page.get_by_label("Your name").fill("Olive")
    page.get_by_role("button", name="Join room").click()
    hand = page.get_by_role("region", name="Your card")
    expect(hand.get_by_role("button", name="XXL", exact=True)).to_be_visible()
    expect(page.get_by_text("Owner", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Settings")).to_be_visible()

    # The delegate gets the session controls but not the settings.
    delegate = browser.new_context()
    dpage = delegate.new_page()
    sign_in(dpage, server, "Dee Delegate", next_path="/r/e2e-renamed")
    expect(dpage.get_by_label("Your name")).to_have_value("Dee Delegate")
    dpage.get_by_role("button", name="Join room").click()
    expect(dpage.get_by_text("Facilitator controls")).to_be_visible()
    expect(dpage.get_by_text("Delegate", exact=True)).to_be_visible()
    expect(dpage.get_by_role("link", name="Settings")).to_have_count(0)
    dpage.goto(f"{server}/r/e2e-renamed/settings")
    expect(dpage.get_by_text("Only the room's owner can change its settings.")).to_be_visible()

    # An outsider, signed in, is just a player.
    outsider = browser.new_context()
    opage = outsider.new_page()
    sign_in(opage, server, "Otto Outsider", next_path="/r/e2e-renamed")
    opage.get_by_role("button", name="Join room").click()
    expect(opage.get_by_role("region", name="Your card")).to_be_visible()
    expect(opage.get_by_text("Facilitator controls")).to_have_count(0)

    for context in (owner, delegate, outsider):
        context.close()


def test_outsider_cannot_create_rooms(browser, server):
    context = browser.new_context()
    page = context.new_page()
    sign_in(page, server, "Otto Outsider")

    expect(page.get_by_role("region", name="Your rooms")).to_be_visible()
    expect(page.get_by_role("button", name="Create room")).to_have_count(0)
    expect(page.get_by_text("cannot create rooms")).to_be_visible()
    context.close()


def test_deleting_a_room_tells_everyone_in_it(browser, server):
    owner = browser.new_context()
    page = owner.new_page()
    sign_in(page, server, "Olive Owner")
    assert owner.request.post(f"{server}/api/rooms", data={"slug": "e2e-gone"}).status == 201

    player = browser.new_context()
    ppage = player.new_page()
    ppage.goto(f"{server}/r/e2e-gone")
    ppage.get_by_label("Your name").fill("Ana")
    ppage.get_by_role("button", name="Join room").click()
    expect(ppage.get_by_role("heading", name="The backlog did not load")).to_be_visible()

    page.goto(f"{server}/r/e2e-gone/settings")
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Delete room").click()
    page.wait_for_url(f"{server}/")

    expect(ppage.get_by_text("The owner deleted this room.")).to_be_visible()
    for context in (owner, player):
        context.close()


def test_pages_link_the_favicon(browser, server):
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{server}/")

    for selector in ['link[rel="icon"][type="image/svg+xml"]', 'link[rel="apple-touch-icon"]']:
        href = page.locator(selector).get_attribute("href")
        response = context.request.get(f"{server}{href}")
        assert response.ok, href
    assert context.request.get(f"{server}/favicon.ico").headers["content-type"].startswith("image/")
    context.close()


def test_open_page_learns_its_room_is_gone_when_it_reconnects(table):
    """A tab left open on a room that no longer exists, say after the rooms file was
    replaced, stops retrying and says so the next time its connection drops."""
    context = table.new_context()
    page = context.new_page()
    sockets = []

    def proxy(ws):
        ws.connect_to_server()
        sockets.append(ws)

    page.route_web_socket(re.compile(r"/ws/rooms/"), proxy)
    page.goto(table.url)
    page.get_by_label("Your name").fill("Ana")
    page.get_by_role("button", name="Join room").click()
    expect(page.locator('[data-player="Ana"]')).to_be_visible()

    # The room disappears from the file behind the server's back, then the socket drops.
    db = sqlite3.connect(table.database)
    with db:
        db.execute("DELETE FROM rooms WHERE slug = ?", (table.slug,))
    db.close()
    sockets[-1].close()

    expect(page.get_by_text(f"There is no room called {table.slug}.")).to_be_visible()
    expect(page.get_by_text("Reconnecting")).to_have_count(0)
    count = len(sockets)
    page.wait_for_timeout(2_500)
    assert len(sockets) == count  # no more retries
    context.close()


def test_every_page_links_the_source_code_in_a_new_tab(table):
    ana = table.join("Ana")
    pages = {"room": ana.page}
    home = table.new_context().new_page()
    home.goto(f"{table.base}/")
    pages["home"] = home

    for name, page in pages.items():
        link = page.get_by_role("contentinfo").get_by_role("link", name="Source on GitHub")
        expect(link).to_have_attribute("href", "https://github.com/nijaba/scrum-poker")
        expect(link).to_have_attribute("target", "_blank")
        assert "noopener" in link.get_attribute("rel"), name
        box = link.bounding_box()
        assert box["height"] >= 44, (name, box)  # the minimum hit target
