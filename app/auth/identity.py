"""A signed-in account, as the session cookie carries it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PROVIDERS = ("google", "github")


@dataclass(frozen=True)
class Identity:
    provider: str  # "google" or "github"
    subject: str  # Google's `sub` or GitHub's numeric user ID: stable across renames
    name: str  # display name, for showing only: never used to grant anything
    email: str | None = None  # Google: verified email, lowercased
    login: str | None = None  # GitHub: login
    domain: str | None = None  # Google: Workspace hosted domain (`hd`), lowercased
    orgs: tuple[str, ...] = field(default=())  # GitHub: allowlisted orgs the user belongs to

    @property
    def key(self) -> tuple[str, str]:
        return (self.provider, self.subject)

    @property
    def label(self) -> str:
        """How the account is named in settings: the email or the GitHub login."""
        return (self.email if self.provider == "google" else self.login) or self.name

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "subject": self.subject,
            "name": self.name,
            "email": self.email,
            "login": self.login,
            "domain": self.domain,
            "orgs": list(self.orgs),
        }

    @staticmethod
    def from_dict(data: Any) -> Identity | None:
        if not isinstance(data, dict) or data.get("provider") not in PROVIDERS:
            return None
        subject, name = data.get("subject"), data.get("name")
        if not isinstance(subject, str) or not subject or not isinstance(name, str):
            return None
        orgs = data.get("orgs") or []
        if not isinstance(orgs, list) or not all(isinstance(o, str) for o in orgs):
            return None
        return Identity(
            provider=data["provider"],
            subject=subject,
            name=name,
            email=_str(data.get("email")),
            login=_str(data.get("login")),
            domain=_str(data.get("domain")),
            orgs=tuple(orgs),
        )


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
