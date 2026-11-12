"""HTTPS behind a proxy: cases HS-01 and HS-02, at Integration level.

TLS ends at a reverse proxy, which tells the app the original scheme in
X-Forwarded-Proto. The app believes that header only from the proxies listed in
FORWARDED_ALLOW_IPS. The test client's address is "testclient".
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import ConfigError, Settings
from app.main import create_app
from app.store.rooms import RoomRecord
from tests.identities import OWNER

SITE = "https://poker.example.com"
HSTS = "max-age=31536000"


def make_app(settings, tmp_path, trusted="testclient"):
    static = tmp_path / "static"
    static.mkdir(exist_ok=True)
    (static / "index.html").write_text("<!doctype html><title>Scrum poker</title>")
    https = Settings(
        **{
            **settings.__dict__,
            "base_url": SITE,
            "providers": {},
            "fake_sso": False,
            "forwarded_allow_ips": trusted,
        }
    )
    app = create_app(settings=https, static_dir=static)
    app.state.store.create(RoomRecord("team-a", OWNER.key, OWNER.label))
    return app


@pytest.fixture
def proxy(settings, tmp_path):
    """Requests as they reach the app from the proxy: plain HTTP on the inside."""
    return TestClient(make_app(settings, tmp_path), base_url="http://poker.example.com")


def test_hs01_plain_http_is_redirected_to_https(proxy):
    response = proxy.get(
        "/r/team-a?x=1", headers={"x-forwarded-proto": "http"}, follow_redirects=False
    )

    assert response.status_code == 308
    assert response.headers["location"] == f"{SITE}/r/team-a?x=1"


def test_hs01_redirect_goes_to_the_configured_host_not_the_requested_one(proxy):
    response = proxy.get(
        "/", headers={"host": "evil.example", "x-forwarded-proto": "http"}, follow_redirects=False
    )

    assert response.headers["location"] == f"{SITE}/"


def test_hs01_a_request_with_no_forwarded_header_counts_as_plain_http(proxy):
    response = proxy.get("/api/me", follow_redirects=False)

    assert response.status_code == 308


def test_hs01_forwarded_header_from_an_untrusted_address_is_ignored(settings, tmp_path):
    app = make_app(settings, tmp_path, trusted="10.0.0.1")
    client = TestClient(app, base_url="http://poker.example.com")

    response = client.get("/", headers={"x-forwarded-proto": "https"}, follow_redirects=False)

    assert response.status_code == 308


def test_hs01_health_check_answers_over_plain_http(proxy):
    response = proxy.get("/healthz", follow_redirects=False)

    assert response.status_code == 200


def test_hs01_plain_websocket_is_refused(proxy):
    with pytest.raises(WebSocketDisconnect), proxy.websocket_connect("/ws/rooms/team-a") as ws:
        ws.receive_json()


def test_hs01_websocket_through_the_proxy_over_tls_connects(proxy):
    with proxy.websocket_connect(
        "/ws/rooms/team-a", headers={"x-forwarded-proto": "https", "origin": SITE}
    ) as ws:
        assert ws.receive_json()["type"] == "state"


def test_hs02_https_responses_carry_hsts(proxy):
    for path in ["/", "/r/team-a", "/api/me", "/healthz"]:
        response = proxy.get(path, headers={"x-forwarded-proto": "https"})
        assert response.status_code == 200, path
        assert response.headers["strict-transport-security"] == HSTS, path


def test_hs02_hsts_also_on_errors_and_redirects(proxy):
    missing = proxy.get("/api/rooms/nope", headers={"x-forwarded-proto": "https"})
    moved = proxy.get("/", follow_redirects=False)

    assert missing.status_code == 404
    assert missing.headers["strict-transport-security"] == HSTS
    assert moved.headers["strict-transport-security"] == HSTS


def test_localhost_serves_plain_http_without_hsts(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "strict-transport-security" not in response.headers


def test_forwarded_allow_ips_comes_from_the_environment():
    env = {"APP_BASE_URL": "http://localhost:8000", "FORWARDED_ALLOW_IPS": "10.0.0.1, 10.0.0.2"}

    assert Settings.from_env(env).forwarded_allow_ips == "10.0.0.1, 10.0.0.2"
    assert Settings.from_env({}).forwarded_allow_ips == "127.0.0.1"


def test_production_settings_refuse_plain_http_base_url():
    with pytest.raises(ConfigError):
        Settings.from_env({"APP_BASE_URL": "http://poker.example.com"})
