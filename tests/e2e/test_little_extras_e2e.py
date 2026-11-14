"""The little extras in a real browser. Cases EE-08 to EE-10."""

from playwright.sync_api import expect

from tests.e2e.conftest import players


def seat(table, *names):
    seats = [table.join(names[0], facilitator=True)] + [table.join(n) for n in names[1:]]
    for s in seats:
        expect(players(s.page)).to_have_count(len(names))
    return seats


def reveal(seats, cards):
    for s, card in zip(seats, cards, strict=True):
        s.vote(card)
    for s in seats:
        expect(s.page.get_by_text(f"{len(seats)} of {len(seats)} voted")).to_be_visible()
    seats[0].press("Reveal cards")


def test_ee08_a_coffee_break_shows_by_the_name_until_the_vote(table):
    fay, ana, ben = seat(table, "Fay", "Ana", "Ben")

    ana.press("Coffee break")

    expect(ana.page.get_by_role("button", name="Coffee break")).to_have_attribute(
        "aria-pressed", "true"
    )
    for s in (fay, ana, ben):
        expect(s.page.get_by_label("Ana needs a break")).to_be_visible()
        expect(s.page.get_by_text("0 of 3 voted")).to_be_visible()

    ana.vote("5")

    for s in (fay, ana, ben):
        expect(s.page.get_by_label("Ana needs a break")).to_have_count(0)
        expect(s.page.get_by_text("1 of 3 voted")).to_be_visible()


def test_ee09_splitting_hint_then_nobody_knows(table):
    fay, ana, ben = seat(table, "Fay", "Ana", "Ben")

    reveal((fay, ana, ben), ("8", "55", "13"))
    for s in (fay, ana, ben):
        expect(s.page.get_by_text("Have you considered splitting this?")).to_be_visible()

    fay.press("Restart vote")
    reveal((fay, ana, ben), ("?", "?", "?"))
    for s in (fay, ana, ben):
        expect(s.page.locator('[data-figure="consensus"]')).to_have_text("Nobody knows. Ship it?")
        expect(s.page.get_by_text("Have you considered splitting this?")).to_have_count(0)


def test_ee10_five_matching_votes_make_a_perfect_consensus(table):
    seats = seat(table, "Fay", "Ana", "Ben", "Cid", "Dee")

    reveal(seats, ["5"] * 5)

    for s in seats:
        expect(s.page.get_by_text("Perfect consensus: everyone chose 5.")).to_be_visible()
        expect(s.page.locator("section.table.perfect")).to_have_count(1)


KONAMI = ["ArrowUp", "ArrowUp", "ArrowDown", "ArrowDown"]
KONAMI += ["ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight", "b", "a"]


def type_konami(page):
    for key in KONAMI:
        page.keyboard.press(key)


def deck(page):
    return page.locator("html")


def test_ee11_the_konami_code_switches_your_own_deck(table):
    fay, ana = seat(table, "Fay", "Ana")
    ana.page.locator("body").click(position={"x": 5, "y": 5})

    type_konami(ana.page)

    expect(deck(ana.page)).to_have_attribute("data-deck", "arcade")
    expect(ana.page.get_by_role("status").filter(has_text="Arcade deck on")).to_be_visible()
    expect(deck(fay.page)).not_to_have_attribute("data-deck", "arcade")

    ana.page.reload()
    expect(ana.page.get_by_role("region", name="Your card")).to_be_visible()
    expect(deck(ana.page)).to_have_attribute("data-deck", "arcade")

    ana.page.locator("body").click(position={"x": 5, "y": 5})
    type_konami(ana.page)
    expect(deck(ana.page)).not_to_have_attribute("data-deck", "arcade")
    expect(ana.page.get_by_role("status").filter(has_text="Classic deck")).to_be_visible()


def test_ee12_the_code_typed_into_a_text_field_does_nothing(table):
    page = table.open(table.new_context())
    field = page.get_by_label("Your name")
    field.click()

    type_konami(page)

    expect(field).to_have_value("ba")
    expect(deck(page)).not_to_have_attribute("data-deck", "arcade")
