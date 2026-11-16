"""Co-owners and handing a room over in a real browser: CO-07 and OT-06.

The rules behind them (CO-01 to CO-05, OT-01 to OT-05) are proved at Integration level.
"""

from playwright.sync_api import expect

from tests.e2e.conftest import sign_in

SLUG = "e2e-co"


def rooms_row(page, slug):
    return (
        page.get_by_role("region", name="Your rooms")
        .get_by_role("listitem")
        .filter(has=page.get_by_role("link", name=slug, exact=True))
    )


def test_co07_ot06_a_co_owner_manages_the_room_then_takes_it_over(browser, server):
    owner = browser.new_context()
    page = owner.new_page()
    page.on("dialog", lambda dialog: dialog.accept())
    sign_in(page, server, "Olive Owner")
    page.get_by_label("Short name").fill(SLUG)
    page.get_by_role("button", name="Create room").click()
    page.wait_for_url(f"{server}/r/{SLUG}/settings")

    # CO-07: the owner makes a delegate a co-owner.
    page.get_by_label("Google email or GitHub username").fill("delegate@example.com")
    page.get_by_role("button", name="Add delegate").click()
    page.get_by_label("Role for delegate@example.com").select_option(label="Co-owner")
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_text("Saved.")).to_be_visible()

    dee = browser.new_context()
    dpage = dee.new_page()
    sign_in(dpage, server, "Dee Delegate")
    row = rooms_row(dpage, SLUG)
    expect(row.get_by_text("Co-owner", exact=True)).to_be_visible()
    expect(row.get_by_role("link", name="Settings")).to_be_visible()

    dpage.goto(f"{server}/r/{SLUG}")
    dpage.get_by_role("button", name="Join room").click()
    expect(dpage.get_by_text("Facilitator controls")).to_be_visible()
    dpage.get_by_role("banner").get_by_role("button", name="Dee Delegate").click()
    dpage.get_by_role("menuitem", name="Room settings").click()
    dpage.wait_for_url(f"{server}/r/{SLUG}/settings")
    expect(dpage.get_by_role("region", name="Delegates")).to_contain_text("owner@example.com")
    expect(dpage.get_by_role("button", name="Delete room")).to_have_count(0)
    expect(dpage.get_by_role("button", name="Make delegate@example.com owner")).to_have_count(0)
    dpage.get_by_role("button", name="Save changes").click()
    expect(dpage.get_by_text("Saved.")).to_be_visible()

    # OT-06: the owner offers the room; the co-owner accepts on the home page.
    page.reload()
    page.get_by_role("button", name="Make delegate@example.com owner").click()
    expect(page.get_by_text("delegate@example.com has until")).to_be_visible()
    expect(page.get_by_role("button", name="Cancel offer")).to_be_visible()

    dpage.goto(server)
    offer = dpage.get_by_role("group", name=f"Ownership offer for {SLUG}")
    expect(offer).to_contain_text(f"owner@example.com offered you ownership of {SLUG}.")
    offer.get_by_role("button", name="Accept").click()
    expect(offer).to_have_count(0)
    expect(rooms_row(dpage, SLUG).get_by_text("Owner", exact=True)).to_be_visible()
    dpage.goto(f"{server}/r/{SLUG}/settings")
    expect(dpage.get_by_role("button", name="Delete room")).to_be_visible()
    expect(dpage.get_by_label("Role for owner@example.com")).to_have_value("co_owner")

    page.goto(server)
    expect(rooms_row(page, SLUG).get_by_text("Co-owner", exact=True)).to_be_visible()
    page.goto(f"{server}/r/{SLUG}/settings")
    expect(page.get_by_role("button", name="Delete room")).to_have_count(0)

    owner.close()
    dee.close()
