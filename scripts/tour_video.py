#!/usr/bin/env python3
"""Record a 30-second video of the facilitator's room tour, to docs/video/tour.webm.

The room, its players and its backlog come from the fakes, as in guide_pictures.py. Players
vote while the tour plays, and the cards are revealed on the "Final points and Confirm" step,
so the video shows the room working as well as the captions. The script prints when each step
starts; docs/video/tour-voiceover.md is timed to those marks.

    (cd frontend && npm run build)
    python scripts/tour_video.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Browser, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guide_pictures import ROOT, Session, start_server  # noqa: E402

OUT = ROOT / "docs" / "video"
SIZE = {"width": 1280, "height": 720}

# How long each step stays on screen, in seconds, and what happens around the room meanwhile.
HOLD = {
    "The ticket": 3.0,
    "The table": 3.2,
    "Your cards": 3.0,
    "The reveal": 3.0,
    "Reveal cards": 2.6,
    "Final points and Confirm": 3.4,
    "The countdown": 2.8,
    "Up next and summary": 2.8,
    "Your menu": 3.2,
}


def record(browser: Browser, base: str, folder: Path) -> Path:
    s = Session(browser, base)
    s.join("Fay", s.owner)  # the owner facilitates; this browser is not recorded
    for name in ("Ana", "Ben", "Cleo", "Dev"):
        s.join(name)

    # The recorded browser: the owner's sign-in and seat, but the tour never offered.
    context = browser.new_context(
        viewport=SIZE,
        record_video_dir=str(folder),
        record_video_size=SIZE,
        storage_state={"cookies": s.owner.cookies(), "origins": []},
    )
    page = context.new_page()
    start = time.monotonic()

    def mark(what: str) -> None:
        print(f"{time.monotonic() - start:5.1f}s  {what}")

    page.goto(s.url)
    offer = page.get_by_role("region", name="Tour offer")
    expect(offer).to_be_visible()
    page.evaluate("document.fonts.ready")
    mark("offer")
    page.wait_for_timeout(2000)
    offer.get_by_role("button", name="Take the tour").click()

    caption = page.locator(".tour-caption")
    for title, hold in HOLD.items():
        expect(caption.get_by_role("heading")).to_have_text(title)
        mark(title)
        ms = int(hold * 1000)
        if title == "The table":
            for name in ("Ana", "Ben", "Cleo"):
                page.wait_for_timeout(ms // 4)
                s.vote(name, "5" if name != "Ben" else "3")
            page.wait_for_timeout(ms // 4)
        elif title == "Your cards":
            page.wait_for_timeout(ms // 3)
            hand = page.get_by_role("region", name="Your card")
            hand.get_by_role("button", name="5", exact=True).click()
            page.wait_for_timeout(ms - ms // 3)
        elif title == "The reveal":
            page.wait_for_timeout(ms // 2)
            s.vote("Dev", "8")
            page.wait_for_timeout(ms - ms // 2)
        elif title == "Final points and Confirm":
            page.get_by_role("button", name="Reveal cards", exact=True).click()
            expect(page.get_by_role("region", name="Final points")).to_be_visible()
            page.wait_for_timeout(ms)
        else:
            page.wait_for_timeout(ms)
        button = "Done" if title == "Your menu" else "Next"
        caption.get_by_role("button", name=button).click()
    mark("done")
    page.wait_for_timeout(800)
    mark("end")

    video = page.video
    context.close()
    assert video
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "tour.webm"
    video.save_as(target)
    return target


def main() -> None:
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        raise SystemExit("build the front end first: (cd frontend && npm run build)")
    with tempfile.TemporaryDirectory() as folder:
        process, base = start_server(Path(folder))
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    target = record(browser, base, Path(folder) / "video")
                finally:
                    browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)
    print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
