"""A demo room in a real browser. Case DR-11."""

import re

from playwright.sync_api import expect

BOT_WAIT = 20_000  # bots play a few seconds after a round opens


def test_dr11_try_a_demo_from_the_home_page(browser, server):
    context = browser.new_context()
    page = context.new_page()
    page.goto(server)

    page.get_by_role("button", name="Try a demo").click()
    page.wait_for_url(re.compile(r"/r/demo-[a-z0-9]{8}$"))
    page.get_by_label("Your name").fill("Vic")
    page.get_by_role("button", name="Join room").click()

    expect(page.get_by_role("note")).to_contain_text("Demo room.")
    expect(page.get_by_text("5 of 5 voted")).not_to_be_visible()
    hand = page.get_by_role("region", name="Your card")
    hand.get_by_role("button", name="5", exact=True).click()
    expect(page.get_by_text("5 of 5 voted")).to_be_visible(timeout=BOT_WAIT)

    page.get_by_role("button", name="Reveal cards", exact=True).click()
    expect(page.get_by_label("Vic played 5")).to_be_visible()
    expect(page.locator('[data-figure="average"]')).not_to_have_text("–")

    page.get_by_role("button", name=re.compile(r"^Confirm [\d.]+ points?$")).click()
    expect(page.get_by_label("Session counter")).to_contain_text("1 ticket")
    expect(page.get_by_label("Backlog counter")).to_contain_text("5 of 12 tickets")

    page.get_by_role("button", name="Add a bot").click()
    expect(page.locator("[data-player]")).to_have_count(6)
    context.close()
