"""The home page in a real browser: cases HP-01 to HP-03 (design.md, "Rooms"), and VR-02."""

from playwright.sync_api import expect

from tests.e2e.conftest import sign_in


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_hp01_signed_out_the_home_page_pitches_the_app(browser, server):
    page = browser.new_page()
    page.goto(server)
    hero = page.get_by_role("banner")
    expect(hero.get_by_role("heading", level=1)).to_contain_text("cards face down")
    expect(hero.get_by_role("button", name="Try a demo")).to_be_visible()
    expect(hero.get_by_role("button", name="Watch the video")).to_be_visible()
    expect(page.get_by_role("heading", name="Run a session")).to_be_visible()
    expect(page.get_by_role("link", name="Sign in with Google")).to_be_visible()
    steps = page.get_by_role("list", name="How a session runs").get_by_role("listitem")
    expect(steps).to_have_count(4)
    page.close()


def test_hp02_signed_in_rooms_are_cards(browser, server):
    page = browser.new_page()
    sign_in(page, server, "Olive Owner")
    expect(page.get_by_role("heading", level=1)).to_have_text("Welcome back, Olive.")
    expect(page.get_by_role("list", name="How a session runs")).to_have_count(0)

    page.get_by_label("Short name").fill("e2e-home")
    page.get_by_role("button", name="Create room").click()
    page.wait_for_url(f"{server}/r/e2e-home/settings")
    page.goto(server)

    rooms = page.get_by_role("region", name="Your rooms")
    card = rooms.get_by_role("listitem").filter(has=page.get_by_role("link", name="e2e-home"))
    expect(card.get_by_text("Owner", exact=True)).to_be_visible()
    # The Create a room card sits in the same grid as the rooms.
    expect(rooms.get_by_role("region", name="Create a room")).to_be_visible()
    # Settings opens the settings; anywhere else on the card opens the room.
    card.get_by_role("link", name="Settings").click()
    page.wait_for_url(f"{server}/r/e2e-home/settings")
    page.goto(server)
    # The room link covers the card, so the click on "Open room" lands on it.
    card.get_by_text("Open room").click(force=True)
    page.wait_for_url(f"{server}/r/e2e-home")
    page.close()


def test_hp03_the_home_page_fits_a_phone(browser, server):
    context = browser.new_context(viewport={"width": 375, "height": 812})
    page = context.new_page()
    page.goto(server)
    expect(page.get_by_role("heading", name="Run a session")).to_be_visible()
    no_sideways_scroll(page)
    sign_in(page, server, "Olive Owner")
    expect(page.get_by_role("region", name="Your rooms")).to_be_visible()
    no_sideways_scroll(page)
    context.close()


def test_vr02_the_footer_shows_the_version_and_links_to_its_notes(browser, server, table):
    from tests.test_health import VERSION

    page = browser.new_page()
    for url in (server, table.url):
        page.goto(url)
        link = page.get_by_role("contentinfo").get_by_role("link", name=f"Version {VERSION}")
        expect(link).to_have_attribute(
            "href", f"https://github.com/nijaba/scrum-poker/releases/tag/v{VERSION}"
        )
    page.close()
