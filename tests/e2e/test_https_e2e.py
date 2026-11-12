"""A room over HTTPS in a real browser: case HS-03.

uvicorn serves TLS with a throwaway self-signed certificate for localhost, standing
in for the proxy. The browser must then reach the room over a secure WebSocket.
"""

import datetime
import ipaddress

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from playwright.sync_api import expect

from tests.e2e.conftest import Table, serve


def self_signed(folder):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_file, key_file = folder / "cert.pem", folder / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_file, key_file


@pytest.fixture
def https_server(tmp_path_factory):
    folder = tmp_path_factory.mktemp("tls")
    with serve(folder, tls=self_signed(folder)) as base:
        yield base


class TlsBrowser:
    """Hands out contexts that accept the test's self-signed certificate."""

    def __init__(self, browser):
        self.browser = browser

    def new_context(self, **kwargs):
        return self.browser.new_context(ignore_https_errors=True, **kwargs)


def test_hs03_room_connects_over_a_secure_websocket(browser, https_server):
    assert https_server.startswith("https://")
    table = Table(TlsBrowser(browser), https_server)
    try:
        context = table.new_context()
        page = context.new_page()
        sockets = []
        page.on("websocket", lambda ws: sockets.append(ws.url))
        page.goto(table.url)
        page.get_by_label("Your name").fill("Ana")
        page.get_by_role("button", name="Join room").click()

        expect(page.locator('[data-player="Ana"]')).to_be_visible()
        expect(page.get_by_role("region", name="Current ticket")).to_be_visible()
        assert sockets, "the page opened no WebSocket"
        assert all(url.startswith("wss://") for url in sockets), sockets
    finally:
        table.close()
