"""Encryption for the Jira refresh tokens kept in the SQLite file (Fernet: AES-128-CBC + HMAC)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def seal(self, token: str) -> str:
        return self._fernet.encrypt(token.encode()).decode()

    def open(self, sealed: str | None) -> str | None:
        """The token, or None if it was sealed with another key or is damaged."""
        if not sealed:
            return None
        try:
            return self._fernet.decrypt(sealed.encode()).decode()
        except (InvalidToken, ValueError):
            return None


def valid_key(key: str) -> bool:
    try:
        Fernet(key.encode())
    except (ValueError, TypeError):
        return False
    return True


def new_key() -> str:
    return Fernet.generate_key().decode()
