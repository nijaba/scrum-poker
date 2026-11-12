"""The app from its container in a real browser: case PK-02.

Skips when Docker is not running. The container runs on localhost with the fake
sign-in, on the same port inside and out, so a browser can create a room and join
it with nothing else set up.
"""

import pytest
from playwright.sync_api import expect

from tests.container import build_image, container, free_port
from tests.e2e.conftest import sign_in


@pytest.fixture(scope="module")
def image() -> str:
    return build_image()


def test_pk02_page_loads_and_room_connects_from_the_container(image, browser):
    port = free_port()
    env = {
        "APP_BASE_URL": f"http://localhost:{port}",
        "SESSION_SECRET": "s" * 40,
        "SCRUM_POKER_FAKE_SSO": "1",
        "ROOM_CREATOR_ALLOWLIST": "owner@example.com",
    }
    with container(image, env, port, same_port=True) as base:
        context = browser.new_context()
        page = context.new_page()
        sockets = []
        page.on("websocket", lambda ws: sockets.append(ws.url))

        sign_in(page, base, "Olive Owner")
        page.get_by_label("Short name").fill("from-docker")
        page.get_by_role("button", name="Create room").click()
        page.wait_for_url(f"{base}/r/from-docker/settings")
        page.goto(f"{base}/r/from-docker")
        page.get_by_label("Your name").fill("Olive")
        page.get_by_role("button", name="Join room").click()

        expect(page.locator('[data-player="Olive"]')).to_be_visible()
        assert f"ws://localhost:{port}/ws/rooms/from-docker" in sockets
        context.close()
