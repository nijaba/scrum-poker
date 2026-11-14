"""The queue filter in a real browser. Case QF-10."""

from playwright.sync_api import expect


def test_qf10_owner_previews_and_saves_the_filter_then_a_session_follows_it(table):
    page = table.owner.new_page()
    page.goto(f"{table.url}/settings")
    section = page.get_by_role("region", name="Queue filter")

    section.get_by_role("button", name="Preview queue").click()
    preview = section.get_by_role("region", name="Queue preview")
    expect(preview.get_by_role("status")).to_contain_text("8 tickets would be in the queue")
    expect(preview.get_by_role("listitem").first).to_contain_text("SHOP-134")

    section.get_by_label("Tickets that already have an estimate").check()
    section.get_by_label("Extra JQL (optional)").fill("labels = checkout")
    section.get_by_role("button", name="Preview queue").click()
    expect(preview.get_by_role("status")).to_contain_text("5 tickets would be in the queue")
    first = preview.get_by_role("listitem").first
    expect(first).to_contain_text("SHOP-131")
    expect(first).to_contain_text("3 points")

    section.get_by_label("Extra JQL (optional)").fill("labels ~~ checkout")
    section.get_by_role("button", name="Preview queue").click()
    expect(section.get_by_role("alert")).to_contain_text("labels ~~ checkout")
    section.get_by_label("Extra JQL (optional)").fill("labels = checkout")

    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_text("Saved.")).to_be_visible()
    page.close()

    olive = table.join("Olive", facilitator=True)
    ticket = olive.page.get_by_role("region", name="Current ticket")
    expect(ticket).to_contain_text("SHOP-131")
    expect(ticket).to_contain_text("Ticket 1 of 5")
    expect(ticket).not_to_contain_text("Jira has it at")
    olive.vote("8")
    olive.press("Reveal cards")
    expect(ticket).to_contain_text("Jira has it at 3 points")
