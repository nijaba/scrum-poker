"""The fake SSO provider's accounts, as identities, plus helpers to act as them in tests."""

from app.auth.identity import Identity
from app.players import COOKIE as PLAYER_COOKIE
from app.players import Player, encode_player

OWNER = Identity(
    "google", "g-owner", "Olive Owner", email="owner@example.com", domain="example.com"
)
DELEGATE = Identity("google", "g-delegate", "Dee Delegate", email="delegate@example.com")
OUTSIDER = Identity("google", "g-outsider", "Otto Outsider", email="outsider@example.org")
GH_OWNER = Identity("github", "1001", "Octo Owner", login="octo-owner")
GH_DELEGATE = Identity("github", "1002", "Octo Delegate", login="octo-delegate")
GH_OUTSIDER = Identity("github", "1003", "Octo Outsider", login="octo-outsider")

BASE = "http://localhost"


def session_value(app, identity: Identity) -> str:
    return app.state.auth.session_value(identity)


def headers(app, identity: Identity | None = None, player: tuple[str, str] | None = None) -> dict:
    """Request headers for one browser: its cookies, and the app's own Origin."""
    cookies = []
    if identity is not None:
        cookies.append(f"sp_session={session_value(app, identity)}")
    if player is not None:
        cookies.append(f"{PLAYER_COOKIE}={encode_player(Player(*player))}")
    result = {"origin": app.state.settings.origin}
    if cookies:
        result["cookie"] = "; ".join(cookies)
    return result


def open_ws(client, path, identity=None, player=None):
    """A room socket for one browser.

    Starlette's test client does not send its cookies on WebSockets; browsers do.
    """
    return client.websocket_connect(path, headers=headers(client.app, identity, player))
