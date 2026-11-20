"""Demo rooms in a real browser. Cases DR-11, DR-13 to DR-17."""

import re

from playwright.sync_api import expect

from tests.e2e.conftest import serve

# Bots play 2 to 7 seconds after a round opens (BOT_DELAY), and one that takes a coffee break
# first waits up to twice that again: 21 seconds at most. Leave room above it.
BOT_WAIT = 30_000


def test_dr11_try_a_demo_from_the_home_page(browser, server):
    context = browser.new_context()
    page = context.new_page()
    page.goto(server)

    page.get_by_role("button", name="Try a demo").click()
    page.wait_for_url(re.compile(r"/r/demo-[a-z0-9]{8}$"))
    page.get_by_label("Your name").fill("Vic")
    page.get_by_role("button", name="Join room").click()

    expect(page.get_by_role("note")).to_contain_text("Demo room.")
    # DR-14: the banner gives the server's idle time (DEMO_IDLE_SECONDS=2700 here)
    expect(page.get_by_role("note")).to_contain_text("ends after 45 minutes with nobody here")
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


def test_dr13_when_every_demo_room_is_taken_the_home_page_says_come_back_later(browser, server):
    context = browser.new_context()
    page = context.new_page()
    detail = "The bots are fully booked. Come back later."
    page.route("**/api/demo", lambda route: route.fulfill(status=503, json={"detail": detail}))
    page.goto(server)

    page.get_by_role("button", name="Try a demo").click()

    note = page.get_by_role("region", name="Try a demo").get_by_role("status")
    expect(note).to_contain_text(detail)
    expect(note).to_contain_text("☕")
    expect(page).not_to_have_url(re.compile(r"/r/demo-"))
    expect(page.get_by_role("button", name="Try a demo")).to_be_enabled()
    context.close()


def test_dr15_the_demo_banner_offers_the_tour_every_time(browser, server):
    context = browser.new_context()  # never offered a tour
    page = context.new_page()
    page.goto(server)
    page.get_by_role("button", name="Try a demo").click()
    page.wait_for_url(re.compile(r"/r/demo-[a-z0-9]{8}$"))
    page.get_by_label("Your name").fill("Vic")
    page.get_by_role("button", name="Join room").click()

    banner = page.get_by_role("note")
    expect(banner).to_contain_text("Demo room.")
    expect(page.get_by_role("region", name="Tour offer")).to_have_count(0)
    banner.get_by_role("button", name="Take the tour").click()
    caption = page.locator(".tour-caption")
    expect(caption.get_by_role("heading")).to_have_text("The ticket")
    expect(caption.locator(".tour-count")).to_have_text("Step 1 of 9")  # the facilitator's tour
    caption.get_by_role("button", name="Close").click()
    expect(caption).to_have_count(0)

    page.reload()
    expect(page.get_by_role("region", name="Your card")).to_be_visible()
    expect(page.get_by_role("region", name="Tour offer")).to_have_count(0)
    page.get_by_role("note").get_by_role("button", name="Take the tour").click()
    expect(caption.get_by_role("heading")).to_have_text("The ticket")
    context.close()


def test_dr16_watch_the_video_from_the_home_page(browser, server):
    context = browser.new_context()
    page = context.new_page()
    page.goto(server)
    demo = page.get_by_role("region", name="Try a demo")
    watch = demo.get_by_role("button", name="Watch the video")
    expect(watch).to_be_visible()
    expect(demo.get_by_role("button", name="Try a demo")).to_be_visible()

    watch.click()
    player = page.get_by_role("dialog", name="Scrum poker in 30 seconds")
    expect(player).to_be_visible()
    video = page.locator("video")  # a closed dialog leaves the accessibility tree
    expect(video).to_have_attribute("src", "/tour.mp4")
    expect(video).to_have_attribute("controls", "")

    page.keyboard.press("Escape")
    expect(player).to_be_hidden()
    page.wait_for_function("document.querySelector('video').paused")

    watch.click()
    expect(player).to_be_visible()
    player.get_by_role("button", name="Close").click()
    expect(player).to_be_hidden()
    page.wait_for_function("document.querySelector('video').paused")
    context.close()


def test_dr17_the_video_button_follows_its_setting(browser, tmp_path):
    # Demo rooms off: the button stands on its own.
    (tmp_path / "solo").mkdir()
    with serve(tmp_path / "solo", extra={"DEMO_ROOMS": "0"}) as base:
        page = browser.new_page()
        page.goto(base)
        expect(page.get_by_role("button", name="Try a demo")).to_have_count(0)
        section = page.get_by_role("region", name="Watch the video")
        section.get_by_role("button", name="Watch the video").click()
        expect(page.get_by_role("dialog", name="Scrum poker in 30 seconds")).to_be_visible()
        page.close()
    # Turned off: no button, with or without demo rooms.
    (tmp_path / "off").mkdir()
    with serve(tmp_path / "off", extra={"TOUR_VIDEO": "0"}) as base:
        page = browser.new_page()
        page.goto(base)
        expect(page.get_by_role("button", name="Try a demo")).to_be_visible()
        expect(page.get_by_role("button", name="Watch the video")).to_have_count(0)
        page.close()


def test_dr21_set_up_a_demo_room_and_run_it(browser, server):
    context = browser.new_context()
    page = context.new_page()
    page.goto(server)
    page.get_by_role("button", name="Try a demo").click()
    page.wait_for_url(re.compile(r"/r/demo-[a-z0-9]{8}$"))
    room_url = page.url
    page.get_by_label("Your name").fill("Vic")
    page.get_by_role("button", name="Join room").click()

    page.get_by_role("note").get_by_role("link", name="Set up this room").click()
    page.wait_for_url(room_url + "/settings")
    expect(page.get_by_role("note").filter(has_text="Demo room.")).to_be_visible()
    jira = page.get_by_role("region", name="Jira")
    expect(jira).to_contain_text("Demo Co")
    expect(jira.get_by_role("link", name="Connect Jira")).to_have_count(0)
    delegates = page.get_by_role("region", name="Delegates")
    expect(delegates).to_contain_text("dana@example.com")
    expect(delegates.get_by_role("button", name="Add delegate")).to_have_count(0)
    expect(page.get_by_role("button", name="Delete room")).to_have_count(0)

    # The preview follows the form, before saving.
    queue = page.get_by_role("region", name="Queue filter")
    queue.get_by_label("Tickets in progress").check()
    queue.get_by_role("button", name="Preview queue").click()
    expect(queue.get_by_role("region", name="Queue preview")).to_contain_text("SHOP-153")

    page.get_by_label("T-shirt").check()
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_text("Saved.")).to_be_visible()

    page.get_by_role("link", name="Back to room").click()
    page.wait_for_url(room_url)
    hand = page.get_by_role("region", name="Your card")
    expect(hand.get_by_role("button", name="XS", exact=True)).to_be_visible()
    # The saved filter applies through Reload backlog, which a demo room offers at any time.
    page.get_by_role("button", name="Reload backlog").click()
    expect(page.get_by_label("Backlog counter")).to_contain_text("of 13 tickets")
    context.close()
