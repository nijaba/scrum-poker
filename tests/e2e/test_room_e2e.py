"""Whole room flows in a real browser, one facilitator and several players.

Cases RE-02, RR-06, RQ-07, RC-04, RX-02, AR-14, AR-15, AR-16 and JC-14 (on the fake backlog).
"""

import re

from playwright.sync_api import expect

from tests.e2e.conftest import players


def seat_three(table):
    fay = table.join("Fay", facilitator=True)
    ana = table.join("Ana")
    ben = table.join("Ben")
    for seat in (fay, ana, ben):
        expect(players(seat.page)).to_have_count(3)
    return fay, ana, ben


def vote_and_reveal(fay, ana, ben, votes=("3", "5", "5")):
    for seat, card in zip((fay, ana, ben), votes, strict=True):
        seat.vote(card)
    for seat in (fay, ana, ben):
        expect(seat.page.get_by_text("3 of 3 voted")).to_be_visible()
    fay.press("Reveal cards")


def test_re02_reveal_turns_every_card_face_up_on_every_screen(table):
    fay, ana, ben = seat_three(table)
    for seat in (fay, ana, ben):
        expect(seat.page.get_by_label("Ana has voted")).to_have_count(0)

    vote_and_reveal(fay, ana, ben, ("3", "8", "5"))

    for seat in (fay, ana, ben):
        page = seat.page
        expect(page.get_by_text("Cards revealed")).to_be_visible()
        expect(page.get_by_label("Fay played 3")).to_be_visible()
        expect(page.get_by_label("Ana played 8")).to_be_visible()
        expect(page.get_by_label("Ben played 5")).to_be_visible()


def test_rr06_all_three_figures_show_on_every_screen(table):
    fay, ana, ben = seat_three(table)

    vote_and_reveal(fay, ana, ben, ("3", "5", "5"))

    for seat in (fay, ana, ben):
        page = seat.page
        expect(page.locator('[data-figure="average"]')).to_have_text("4.3")
        expect(page.locator('[data-figure="median"]')).to_have_text("5")
        expect(page.locator('[data-figure="consensus"]')).to_have_text("No consensus")
        expect(page.get_by_text("Most chosen: 5 (2 of 3)")).to_be_visible()


def test_rq07_every_screen_follows_a_full_session(table):
    fay, ana, ben = seat_three(table)
    everyone = (fay, ana, ben)

    def all_show(key, session, backlog):
        for seat in everyone:
            page = seat.page
            region = page.get_by_role("region", name="Current ticket")
            expect(region.get_by_text(key, exact=True)).to_be_visible()
            expect(page.get_by_label("Session counter")).to_contain_text(session)
            expect(page.get_by_label("Backlog counter")).to_contain_text(backlog)

    all_show("SHOP-134", "0 tickets · 0 points", "4 of 12 tickets · 16 points")

    vote_and_reveal(fay, ana, ben, ("5", "5", "5"))
    fay.press("Confirm 5 points")
    all_show("SHOP-138", "1 ticket · 5 points", "5 of 12 tickets · 21 points")

    fay.press("Skip")
    all_show("SHOP-139", "1 ticket · 5 points", "5 of 12 tickets · 21 points")

    fay.press("Rewind")
    all_show("SHOP-138", "1 ticket · 5 points", "5 of 12 tickets · 21 points")
    for seat in everyone:
        expect(seat.page.get_by_text("Skipped earlier.")).to_be_visible()

    fay.press("Rewind")
    all_show("SHOP-134", "1 ticket · 5 points", "5 of 12 tickets · 21 points")
    for seat in everyone:
        expect(seat.page.get_by_text("Estimated earlier at 5 points.")).to_be_visible()


def _seconds(text: str) -> int:
    m, s = re.fullmatch(r"\s*(\d+):(\d\d)\s*", text).groups()
    return int(m) * 60 + int(s)


def test_rc04_player_joining_mid_countdown_sees_the_same_time(table):
    fay = table.join("Fay", facilitator=True)
    fay.press("Start")
    big = fay.page.get_by_test_id("countdown-time")
    expect(fay.page.get_by_text("Running")).to_be_visible()
    fay.page.wait_for_timeout(2_500)

    ana = table.join("Ana")
    small = ana.page.get_by_label("Countdown")
    expect(small).to_have_text(re.compile(r"\d:\d\d"))

    late = _seconds(small.inner_text())
    host = _seconds(big.inner_text())
    assert late <= 28
    assert abs(late - host) <= 1


def test_rx02_departed_player_returns_after_reset_as_a_new_seat(table):
    fay = table.join("Fay", facilitator=True)
    ana = table.join("Ana")
    ben = table.join("Ben")
    expect(players(fay.page)).to_have_count(3)

    ben.page.close()  # Ben leaves; his seat stays until the reset
    expect(fay.page.get_by_text("Away")).to_be_visible()
    fay.press("Reset room")
    expect(players(fay.page)).to_have_count(2)  # Fay and Ana checked in
    fay.page.wait_for_timeout(5_500)  # the check-in window closes

    page = table.open(ben.context)
    expect(page.get_by_label("Your name")).to_have_count(0)  # name from the cookie
    expect(page.get_by_role("region", name="Your card")).to_be_visible()
    for p in (fay.page, ana.page, page):
        expect(players(p)).to_have_count(3)
        expect(p.locator('[data-player="Ben"]')).to_have_count(1)


def test_ar14_player_joins_by_link_with_a_name_and_no_sign_in(table):
    context = table.new_context()
    page = table.open(context)

    expect(page.get_by_role("heading", name=f"Join {table.slug}")).to_be_visible()
    page.get_by_label("Your name").fill("Ana")
    page.get_by_role("button", name="Join room").click()

    expect(page.locator('[data-player="Ana"]')).to_be_visible()
    expect(page.get_by_role("region", name="Your card")).to_be_visible()
    expect(page.get_by_text("Facilitator controls")).to_have_count(0)
    cookie = next(c for c in context.cookies() if c["name"] == "sp_player")
    assert cookie["expires"] - __import__("time").time() > 360 * 24 * 3600


def test_ar15_returning_player_skips_the_name_prompt(table):
    ana = table.join("Ana")
    ana.page.close()

    page = table.open(ana.context)

    expect(page.get_by_role("region", name="Your card")).to_be_visible()
    expect(page.get_by_label("Your name")).to_have_count(0)
    expect(page.locator('[data-player="Ana"]')).to_have_count(1)


def test_ar16_dropped_connection_gets_the_same_seat_back(table):
    fay = table.join("Fay", facilitator=True)
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
    page.get_by_role("region", name="Your card").get_by_role("button", name="8").click()
    expect(fay.page.get_by_text("1 of 2 voted")).to_be_visible()

    sockets[-1].close()  # the network drops this browser's socket
    expect(fay.page.locator('[data-player="Ana"]')).to_contain_text("Away")

    expect(fay.page.locator('[data-player="Ana"]')).to_contain_text("Voted", timeout=10_000)
    assert len(sockets) == 2  # the page reconnected by itself
    card = page.get_by_role("region", name="Your card").get_by_role("button", name="8")
    expect(card).to_have_attribute("aria-pressed", "true")
    expect(players(fay.page)).to_have_count(2)


def test_jc14_ticket_card_shows_the_ticket_details(table):
    ana = table.join("Ana")
    card = ana.page.get_by_role("region", name="Current ticket")

    link = card.get_by_role("link", name="SHOP-134")
    expect(link).to_have_attribute("href", "https://shop.atlassian.net/browse/SHOP-134")
    for text in ["Story", "Medium priority", "Epic: Checkout revamp", "checkout", "Ticket 1 of 8"]:
        expect(card.get_by_text(text, exact=True)).to_be_visible()
    expect(card.get_by_role("heading", name="Order confirmation page redesign")).to_be_visible()

    description = card.locator("#ticket-description")
    collapsed = description.bounding_box()["height"]
    more = card.get_by_role("button", name="Show more")
    expect(more).to_have_attribute("aria-expanded", "false")
    more.click()
    expect(card.get_by_role("button", name="Show less")).to_be_visible()
    assert description.bounding_box()["height"] > collapsed * 1.5


def test_ar19_a_taken_name_is_refused_and_another_one_joins(table):
    fay = table.join("Fay", facilitator=True)
    ana = table.join("Ana")

    page = table.open(table.new_context())
    page.get_by_label("Your name").fill("ana")
    page.get_by_role("button", name="Join room").click()

    expect(page.get_by_role("alert")).to_contain_text("Someone at the table is already called Ana")
    expect(page.get_by_label("Your name")).to_have_value("ana")
    expect(players(fay.page)).to_have_count(2)

    page.get_by_label("Your name").fill("Ana B")
    page.get_by_role("button", name="Join room").click()
    expect(page.get_by_role("region", name="Your card")).to_be_visible()
    expect(players(ana.page)).to_have_count(3)

    # Next time, with "Ana B" saved, this browser goes straight back in.
    page.reload()
    expect(page.get_by_role("region", name="Your card")).to_be_visible()
