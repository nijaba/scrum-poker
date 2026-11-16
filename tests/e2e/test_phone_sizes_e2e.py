"""Every screen at the common phone sizes. Case PH-07 (design.md, "Phones").

One browser per person, resized through the sizes, so the whole sweep stays quick. Each
problem is collected rather than stopping at the first, so one run reports them all.
"""

import re

from playwright.sync_api import Page, expect

from tests.e2e.test_phone_e2e import open_menu
from tests.e2e.test_room_e2e import seat_three

# Portrait CSS sizes of common phones: small Android, iPhone SE, iPhone 13 to 16,
# Pixel 8, large Android, iPhone Pro Max.
SIZES = {
    "Android 360": (360, 800),
    "iPhone SE": (375, 667),
    "iPhone 15": (390, 844),
    "Pixel 8": (412, 915),
    "Galaxy S": (384, 832),
    "iPhone Pro Max": (430, 932),
}

# Controls wider than the window, or past its edge, are the usual phone layout faults.
OFF_SCREEN = """() => {
  const doc = document.documentElement;
  const w = doc.clientWidth;
  const out = [];
  if (doc.scrollWidth > w + 1) out.push(`page is ${doc.scrollWidth}px wide`);
  // A row meant to scroll sideways, such as the docked final points, may hold more than fits;
  // the row itself must still fit.
  const insideScroller = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      if (["auto", "scroll"].includes(getComputedStyle(p).overflowX)) return true;
    }
    return false;
  };
  const parts = "button, a, input, select, h1, h2, [role=region]";
  for (const el of document.querySelectorAll(parts)) {
    const r = el.getBoundingClientRect();
    if (!r.width || getComputedStyle(el).visibility === "hidden") continue;
    if (el.closest("dialog:not([open])")) continue;
    if (insideScroller(el)) continue;
    if (r.left < -1 || r.right > w + 1) {
      const label = el.getAttribute("aria-label") || el.textContent || el.tagName;
      const name = label.trim().slice(0, 40);
      out.push(`${name} runs off the side (${Math.round(r.left)} to ${Math.round(r.right)})`);
    }
  }
  return out;
}"""


def check(page: Page, where: str, problems: list[str], in_view=()) -> None:
    """No sideways scrolling or cut-off controls; the given parts fully on screen."""
    problems += [f"{where}: {p}" for p in page.evaluate(OFF_SCREEN)]
    width, height = page.viewport_size["width"], page.viewport_size["height"]
    for label, locator in in_view:
        box = locator.bounding_box()
        if box is None:
            problems.append(f"{where}: {label} is not on screen")
        elif (
            box["y"] < -0.5
            or box["y"] + box["height"] > height + 0.5
            or box["x"] < -0.5
            or box["x"] + box["width"] > width + 0.5
        ):
            problems.append(f"{where}: {label} is not fully in view ({box})")


def final_picks(page: Page):
    return page.locator(".dock").get_by_role("region", name="Final points").locator(".pick")


def sweep(pages, where, problems, in_view=lambda page: ()):
    for name, (width, height) in SIZES.items():
        for page in pages:
            page.set_viewport_size({"width": width, "height": height})
        for page in pages:
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(50)  # one frame for the layout to settle
            check(page, f"{where} at {name}", problems, in_view(page))


def test_ph07_every_screen_fits_common_phones(browser, server, table):
    problems: list[str] = []

    # Home, signed out and signed in, and the join form.
    visitor = browser.new_page()
    visitor.goto(server)
    expect(visitor.get_by_role("heading", name="Run a session")).to_be_visible()
    sweep([visitor], "home signed out", problems)
    visitor.goto(table.url)
    expect(visitor.get_by_label("Your name")).to_be_visible()
    sweep(
        [visitor],
        "join form",
        problems,
        lambda p: [("Join room", p.get_by_role("button", name="Join room"))],
    )
    visitor.close()

    owner = table.owner.new_page()
    owner.goto(server)
    expect(owner.get_by_role("region", name="Your rooms")).to_be_visible()
    sweep([owner], "home signed in", problems)
    owner.goto(f"{table.url}/settings")
    expect(owner.get_by_role("region", name="Delegates")).to_be_visible()
    sweep([owner], "settings", problems)
    owner.close()

    # The room while voting: a player's hand and the facilitator's dock in view.
    fay, ana, ben = seat_three(table)
    hand = lambda p: [  # noqa: E731
        ("the hand", p.get_by_role("region", name="Your card")),
        ("the ticket title", p.get_by_role("heading", level=1)),
    ]
    sweep([ana.page], "player voting", problems, hand)
    sweep(
        [fay.page],
        "facilitator voting",
        problems,
        lambda p: [
            ("Reveal cards", p.locator(".dock").get_by_role("button", name=re.compile("^Reveal")))
        ],
    )

    # After the reveal: the final points and Confirm in the facilitator's dock.
    for seat, card in ((fay, "3"), (ana, "5"), (ben, "5")):
        seat.vote(card)
    expect(fay.page.get_by_text("3 of 3 voted")).to_be_visible()
    fay.page.locator(".dock").get_by_role("button", name=re.compile("^Reveal")).click()
    sweep([ana.page], "player revealed", problems)
    sweep(
        [fay.page],
        "facilitator revealed",
        problems,
        lambda p: [
            ("Confirm", p.locator(".dock").get_by_role("button", name=re.compile("^Confirm"))),
            ("the first final points card", final_picks(p).first),
            ("the last final points card", final_picks(p).last),
        ],
    )

    # The facilitator's sheet and the menu.
    fay.page.set_viewport_size({"width": 375, "height": 667})
    fay.page.get_by_role("button", name="More controls").click()
    sheet = fay.page.get_by_role("dialog")
    expect(sheet).to_be_visible()
    sweep(
        [fay.page],
        "facilitator sheet",
        problems,
        lambda p: [("Close", p.get_by_role("dialog").get_by_role("button", name="Close"))],
    )
    fay.page.keyboard.press("Escape")

    # Remote view: every card in view.
    ana.page.set_viewport_size({"width": 375, "height": 667})
    fay.page.set_viewport_size({"width": 1280, "height": 820})  # Restart vote in the panel
    fay.press("Restart vote")
    open_menu(ana).get_by_role("menuitemcheckbox", name="Remote view").click()
    remote = ana.page.get_by_role("region", name="Remote view")
    expect(remote).to_be_visible()
    sweep(
        [ana.page],
        "remote view",
        problems,
        lambda p: [
            (
                "the last card",
                p.get_by_role("region", name="Remote view").get_by_role("button").last,
            )
        ],
    )

    assert not problems, "\n".join(problems)
