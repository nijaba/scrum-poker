"""Hide my card, for someone sharing their screen.

Cases SS-01 to SS-03 (design.md, "Sharing your screen").
"""

from playwright.sync_api import expect

from tests.e2e.test_mini_e2e import NO_PIP, mini_card, open_mini
from tests.e2e.test_room_e2e import seat_three


def switch(page):
    return page.get_by_role("region", name="Your card").get_by_role("button", name="Hide my card")


LOOKS = """el => { const c = getComputedStyle(el);
  return [c.transform, c.borderColor, c.borderWidth, c.boxShadow, c.zIndex, c.outlineStyle]; }"""


def looks(locator) -> list[str]:
    """How the card is drawn: its lift, edge, shadow and stacking, with the pointer away.

    Styles rather than pixels: a note above the hand changing length moves the cards by a
    fraction of a pixel, and tilted cards then rasterize slightly differently."""
    locator.page.mouse.move(0, 0)
    locator.page.wait_for_timeout(250)  # let the chosen card's lift settle
    return locator.evaluate(LOOKS)


def test_ss01_a_hidden_choice_looks_like_any_other_card(table):
    fay, ana, ben = seat_three(table)
    page = fay.page
    before = looks(fay.card("5"))

    switch(page).click()
    expect(switch(page)).to_have_attribute("aria-pressed", "true")
    fay.card("5").click()
    expect(fay.card("5")).to_have_attribute("aria-pressed", "true")  # screen readers still know
    assert looks(fay.card("5")) == before, "the chosen card is marked on screen"
    expect(page.get_by_role("region", name="Your card")).to_contain_text("chosen")
    expect(ana.page.get_by_label("Fay has voted")).to_be_visible()

    ana.vote("3")
    ben.vote("8")
    fay.press("Reveal cards")
    expect(page.get_by_label("Fay played 5")).to_be_visible()


def test_ss02_the_switch_is_remembered_and_turns_off(table):
    fay, ana, ben = seat_three(table)
    page = fay.page
    switch(page).click()
    fay.card("8").click()
    page.reload()
    expect(switch(page)).to_have_attribute("aria-pressed", "true")
    hidden = looks(fay.card("8"))

    switch(page).click()
    expect(switch(page)).to_have_attribute("aria-pressed", "false")
    assert looks(fay.card("8")) != hidden, "turning the switch off should mark the card again"


def test_ss03_mini_mode_keeps_the_choice_hidden_too(table):
    table.owner.add_init_script(NO_PIP)
    fay, ana, ben = seat_three(table)
    switch(fay.page).click()
    mini = open_mini(fay)
    before = looks(mini_card(mini, "13"))

    mini_card(mini, "13").click()
    expect(fay.card("13")).to_have_attribute("aria-pressed", "true")
    view = mini.get_by_role("region", name="Mini room")
    expect(view).not_to_contain_text("You voted 13")
    expect(view).to_contain_text("chosen")
    assert looks(mini_card(mini, "13")) == before, "the mini view marks the chosen card"
