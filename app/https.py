"""HTTPS behind a reverse proxy.

TLS ends at a proxy or load balancer in front of the container. The proxy sends
plain HTTP to the app and says what the visitor used in X-Forwarded-Proto. The app
believes that header only from the addresses in FORWARDED_ALLOW_IPS.

Outside localhost:
- a plain-HTTP request is redirected (308) to the same path on APP_BASE_URL, never
  to the Host the request named; /healthz answers anyway, for health checks;
- a plain WebSocket is refused;
- every response carries HSTS and the defensive headers below.
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

# Sent on every response outside localhost. HSTS keeps the browser on TLS; the rest are
# cheap defence-in-depth: no MIME sniffing, no framing (clickjacking), a lean referrer.
# The CSP sets only frame-ancestors, so it never interferes with the single-page app's
# own scripts or styles.
SECURITY_HEADERS = (
    (b"strict-transport-security", b"max-age=31536000"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"content-security-policy", b"frame-ancestors 'none'"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
)
HEALTH = "/healthz"


class RequireHttps:
    def __init__(self, app: ASGIApp, base_url: str) -> None:
        self.app = app
        self.base_url = base_url.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        kind = scope["type"]
        if kind == "websocket" and scope.get("scheme") != "wss":
            await send({"type": "websocket.close", "code": 1008})
            return
        if kind != "http":
            await self.app(scope, receive, send)
            return

        async def with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *SECURITY_HEADERS]
            await send(message)

        if scope.get("scheme") == "https" or scope["path"] == HEALTH:
            await self.app(scope, receive, with_security_headers)
            return

        query = scope.get("query_string", b"").decode("latin-1")
        target = self.base_url + scope["path"] + (f"?{query}" if query else "")
        await with_security_headers(
            {
                "type": "http.response.start",
                "status": 308,
                "headers": [(b"location", target.encode()), (b"content-length", b"0")],
            }
        )
        await send({"type": "http.response.body", "body": b""})


def add_https(app: FastAPI, base_url: str, forwarded_allow_ips: str) -> None:
    """Read the proxy's headers first, then require HTTPS. The last middleware added runs first."""
    trusted = [h.strip() for h in forwarded_allow_ips.split(",") if h.strip()]
    app.add_middleware(RequireHttps, base_url=base_url)
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)
