"""The setup checklist on a room's settings page. Cases GS-01 and GS-02 (design.md, "Tour")."""

from playwright.sync_api import expect

from tests.e2e.conftest import TOURS_SEEN, sign_in

STEPS = [
    "Connect Jira",
    "Choose the board",
    "Preview the queue",
    "Add a delegate (optional)",
    "Share the room link",
]


def checklist(page):
    return page.get_by_role("region", name="Get this room ready")


def done(page, step):
    item = checklist(page).get_by_role("listitem").filter(has_text=step)
    expect(item).to_have_attribute("data-done", "true")


def to_do(page, step):
    item = checklist(page).get_by_role("listitem").filter(has_text=step)
    expect(item).to_have_attribute("data-done", "false")


def test_gs01_the_checklist_walks_the_owner_through_setup(browser, server):
    context = browser.new_context()
    context.add_init_script(TOURS_SEEN)
    page = context.new_page()
    sign_in(page, server, "Olive Owner")
    page.get_by_label("Short name").fill("e2e-setup")
    page.get_by_role("button", name="Create room").click()
    page.wait_for_url(f"{server}/r/e2e-setup/settings")

    expect(checklist(page).get_by_role("listitem")).to_have_count(len(STEPS))
    for step in STEPS:
        to_do(page, step)
    expect(checklist(page)).not_to_contain_text("ready to run a session")

    checklist(page).get_by_role("link", name="Connect Jira").click()
    page.get_by_role("link", name="Accept").click()
    page.wait_for_url(f"{server}/r/e2e-setup/settings?jira=connected")
    done(page, "Connect Jira")
    to_do(page, "Choose the board")

    page.get_by_label("Board").select_option(label="SHOP board")
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_text("Saved.")).to_be_visible()
    done(page, "Choose the board")
    expect(checklist(page)).to_contain_text("ready to run a session")

    page.get_by_role("button", name="Preview queue").click()
    expect(page.get_by_role("region", name="Queue filter")).to_contain_text("SHOP-")
    done(page, "Preview the queue")

    page.get_by_label("Google email or GitHub username").fill("delegate@example.com")
    page.get_by_role("button", name="Add delegate").click()
    page.get_by_role("button", name="Save changes").click()
    done(page, "Add a delegate (optional)")

    checklist(page).get_by_role("button", name="Copy link").click()
    done(page, "Share the room link")
    expect(checklist(page).get_by_role("link", name="Open the room")).to_have_attribute(
        "href", "/r/e2e-setup"
    )

    # Ready when the page opens: no checklist.
    page.reload()
    expect(page.get_by_role("region", name="Delegates")).to_be_visible()
    expect(checklist(page)).to_have_count(0)
    context.close()


def test_gs02_a_room_ready_to_run_shows_no_checklist(table):
    page = table.owner.new_page()
    page.goto(f"{table.url}/settings")
    expect(page.get_by_role("region", name="Delegates")).to_be_visible()
    expect(checklist(page)).to_have_count(0)
