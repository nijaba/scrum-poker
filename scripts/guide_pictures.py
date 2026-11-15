#!/usr/bin/env python3
"""Take the pictures in docs/images/ for the user and admin guides (design.md, "Guide pictures").

The app runs on a free port with the fake sign-in, the fake Jira and the fake backlog, so the
pictures show only made-up people and tickets. Playwright's Chromium drives it.

    (cd frontend && npm run build)
    python scripts/guide_pictures.py            # every picture
    python scripts/guide_pictures.py tour.png   # just these

Run it again whenever a screen in a picture changes, and commit the new PNGs.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
BACKLOG = ROOT / "tests" / "fixtures" / "fake_backlog.json"
SLUG = "team-a"
DESKTOP = {"width": 1280, "height": 820}
PHONE = {"width": 440, "height": 956}
TOURS_SEEN = """try {
  localStorage.setItem("scrum-poker-tour-room", "seen");
  localStorage.setItem("scrum-poker-tour-settings", "seen");
} catch (e) {}"""

expect.set_options(timeout=10_000)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(folder: Path) -> tuple[subprocess.Popen, str]:
    backlog = folder / "backlog.json"
    backlog.write_text(BACKLOG.read_text())
    port = free_port()
    base = f"http://localhost:{port}"
    env = {
        **os.environ,
        "SCRUM_POKER_FAKE_BACKLOG": str(backlog),
        "SCRUM_POKER_FAKE_SSO": "1",
        "SCRUM_POKER_FAKE_JIRA": "1",
        "DEMO_ROOMS": "1",
        "APP_BASE_URL": base,
        "ROOM_CREATOR_ALLOWLIST": "owner@example.com",
        "DATABASE_PATH": str(folder / "rooms.sqlite3"),
        "SESSION_SECRET": "pictures-" + "x" * 32,
    }
    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)]
    process = subprocess.Popen(
        command + ["--workers", "1"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{base}/healthz", timeout=0.5)
            return process, base
        except OSError:
            time.sleep(0.1)
    process.terminate()
    raise SystemExit("the app did not start")


class Session:
    """One room with an owner who facilitates and four players, each in their own browser."""

    def __init__(self, browser: Browser, base: str) -> None:
        self.browser = browser
        self.base = base
        self.url = f"{base}/r/{SLUG}"
        self.owner = self.context()
        page = self.owner.new_page()
        page.goto(f"{base}/auth/google/login?next=/")
        page.get_by_role("link", name="Olive Owner").click()
        page.wait_for_url(f"{base}/")
        assert self.owner.request.post(f"{base}/api/rooms", data={"slug": SLUG}).status == 201
        page.goto(f"{self.url}/settings")
        page.get_by_role("link", name="Connect Jira").click()
        page.get_by_role("link", name="Accept").click()
        page.wait_for_url(f"{self.url}/settings?jira=connected")
        page.get_by_label("Board").select_option(label="SHOP board")
        page.get_by_role("button", name="Save changes").click()
        expect(page.get_by_text("Saved.")).to_be_visible()
        self.owner_page = page
        self.seats: dict[str, Page] = {}

    def context(self, phone: bool = False, tours_seen: bool = True, **options) -> BrowserContext:
        size = PHONE if phone else DESKTOP
        context = self.browser.new_context(
            viewport=size, device_scale_factor=2 if phone else 1, **options
        )
        if tours_seen:
            context.add_init_script(TOURS_SEEN)
        return context

    def join(self, name: str, context: BrowserContext | None = None) -> Page:
        page = (context or self.context()).new_page()
        page.goto(self.url)
        page.get_by_label("Your name").fill(name)
        page.get_by_role("button", name="Join room").click()
        expect(page.get_by_role("region", name="Your card")).to_be_visible()
        self.seats[name] = page
        return page

    def vote(self, name: str, card: str) -> None:
        hand = self.seats[name].get_by_role("region", name="Your card")
        hand.get_by_role("button", name=card, exact=True).click()


def settle(page: Page) -> None:
    """Fonts loaded and no pointer hovering over anything."""
    page.evaluate("document.fonts.ready")
    page.mouse.move(0, 0)
    page.wait_for_timeout(300)


def shot(page: Page, name: str, region=None) -> None:
    settle(page)
    path = OUT / name
    if region is None:
        page.screenshot(path=path)
    else:
        region.screenshot(path=path)
    print(f"wrote docs/images/{name}")


def take(browser: Browser, base: str, wanted: set[str]) -> None:
    def want(name: str) -> bool:
        return not wanted or name in wanted

    # Before anyone signs in: the home page as a visitor sees it.
    visitor = browser.new_context(viewport=DESKTOP)
    page = visitor.new_page()
    page.goto(base)
    expect(page.get_by_role("heading", name="Run a session")).to_be_visible()
    if want("home-signed-out.png"):
        shot(page, "home-signed-out.png")
    visitor.close()

    s = Session(browser, base)
    owner = s.owner_page

    if want("home-rooms.png"):
        owner.goto(base)
        expect(owner.get_by_role("region", name="Your rooms")).to_contain_text(SLUG)
        shot(owner, "home-rooms.png")

    # The settings page, section by section.
    owner.goto(f"{s.url}/settings")
    expect(owner.get_by_role("region", name="Jira")).to_contain_text("Connected")
    if want("settings-jira.png"):
        shot(owner, "settings-jira.png", owner.get_by_role("region", name="Jira"))
    if want("settings-queue-filter.png"):
        section = owner.get_by_role("region", name="Queue filter")
        section.get_by_role("button", name="Preview queue").click()
        expect(section.get_by_role("region", name="Queue preview")).to_be_visible()
        shot(owner, "settings-queue-filter.png", section)
    if want("settings-delegates.png"):
        section = owner.get_by_role("region", name="Delegates")
        section.get_by_label("Google email or GitHub username").fill("dana@example.com")
        section.get_by_role("button", name="Add delegate").click()
        owner.get_by_role("button", name="Save changes").click()
        expect(owner.get_by_text("Saved.")).to_be_visible()
        shot(owner, "settings-delegates.png", section)

    # A player arriving by the link.
    newcomer = s.context().new_page()
    newcomer.goto(s.url)
    expect(newcomer.get_by_label("Your name")).to_be_visible()
    if want("join.png"):
        shot(newcomer, "join.png")
    newcomer.context.close()

    # The table: the owner facilitates, four players.
    fay = s.join("Fay", s.owner)
    s.join("Ana")
    s.join("Ben")
    s.join("Cleo")
    s.join("Dev")
    fay.get_by_role("button", name="Sound off").click()  # the room's sound on, so Mute shows
    for name, card in (("Ana", "5"), ("Ben", "3"), ("Cleo", "5")):
        s.vote(name, card)
    expect(fay.get_by_text("3 of 5 voted")).to_be_visible()

    if want("room-player.png"):
        shot(s.seats["Ana"], "room-player.png")
    if want("room-facilitator.png"):
        shot(fay, "room-facilitator.png")
    if want("menu.png"):
        ana = s.seats["Ana"]
        ana.get_by_role("banner").get_by_role("button", name="Ana").click()
        menu = ana.get_by_role("menu")
        expect(menu).to_be_visible()
        settle(ana)
        box = menu.bounding_box()
        assert box
        clip = {
            "x": box["x"] - 220,
            "y": 0,
            "width": box["width"] + 240,
            "height": box["y"] + box["height"] + 20,
        }
        ana.screenshot(path=OUT / "menu.png", clip=clip)
        print("wrote docs/images/menu.png")
        ana.keyboard.press("Escape")

    if want("tour.png") or want("tour-offer.png"):
        context = s.context(tours_seen=False)
        page = s.join("Eve", context)
        expect(page.get_by_role("region", name="Tour offer")).to_be_visible()
        if want("tour-offer.png"):
            shot(page, "tour-offer.png")
        page.get_by_role("button", name="Take the tour").click()
        page.get_by_role("button", name="Next").click()
        page.get_by_role("button", name="Next").click()
        expect(page.get_by_role("heading", name="Your cards")).to_be_visible()
        shot(page, "tour.png")
        page.keyboard.press("Escape")
        page.get_by_role("banner").get_by_role("button", name="Eve").click()
        page.get_by_role("menuitem", name="Log out").click()
        expect(page.get_by_label("Your name")).to_be_visible()
        context.close()
        del s.seats["Eve"]

    # Phones, mid-vote.
    phone = s.context(phone=True)
    gus = s.join("Gus", phone)
    if want("phone-player.png"):
        shot(gus, "phone-player.png")
    fay_phone = s.context(phone=True).new_page()
    # The facilitator on a phone: the owner's sign-in, in a phone-sized browser.
    fay_phone.context.add_cookies(s.owner.cookies())
    fay_phone.goto(s.url)
    expect(fay_phone.locator(".dock")).to_be_visible()
    if want("phone-facilitator.png"):
        shot(fay_phone, "phone-facilitator.png")
    remote = s.join("Hana", s.context(phone=True))
    remote.get_by_role("banner").get_by_role("button", name="Hana").click()
    remote.get_by_role("menuitemcheckbox", name="Remote view").click()
    expect(remote.get_by_role("region", name="Remote view")).to_be_visible()
    remote.get_by_role("button", name="8", exact=True).click()
    if want("phone-remote.png"):
        shot(remote, "phone-remote.png")

    # Dark mode, then the reveal.
    if want("dark-mode.png"):
        dark = s.seats["Ben"]
        dark.emulate_media(color_scheme="dark")
        shot(dark, "dark-mode.png")
        dark.emulate_media(color_scheme="light")

    s.vote("Dev", "8")
    s.vote("Fay", "5")
    s.vote("Gus", "5")
    fay.get_by_role("button", name="Reveal cards", exact=True).click()
    expect(fay.get_by_role("region", name="Final points")).to_be_visible()
    if want("room-revealed.png"):
        shot(fay, "room-revealed.png")
    if want("phone-revealed.png"):
        expect(fay_phone.get_by_role("region", name="Final points")).to_be_visible()
        shot(fay_phone, "phone-revealed.png")
    if want("phone-remote-revealed.png"):
        expect(remote.get_by_label("Most chosen: 5")).to_be_visible()
        shot(remote, "phone-remote-revealed.png")


def main(argv: list[str]) -> None:
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        raise SystemExit("build the front end first: (cd frontend && npm run build)")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        process, base = start_server(Path(folder))
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    take(browser, base, set(argv))
                finally:
                    browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main(sys.argv[1:])
