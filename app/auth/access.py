"""Who may do what in a room: the owner, a co-owner, a delegate, or nobody special.

Delegates (co-owners among them) match on a Google account's verified email or a GitHub
login, never on display name, which anyone can change. The owner matches on the provider's
stable account ID.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.auth.identity import Identity

if TYPE_CHECKING:
    from app.store.rooms import Delegate

OWNER = "owner"
CO_OWNER = "co_owner"
DELEGATE = "delegate"

# Delegate roles, as stored and sent: a facilitator runs sessions, a co-owner also manages.
FACILITATOR_ROLE = "facilitator"
CO_OWNER_ROLE = "co_owner"
ROLES = (FACILITATOR_ROLE, CO_OWNER_ROLE)

MANAGERS = (OWNER, CO_OWNER)


def matches(identity: Identity, provider: str, identifier: str) -> bool:
    """Is this the account a delegate entry names, by verified email or GitHub login?"""
    if provider != identity.provider:
        return False
    if provider == "google":
        return identity.email == identifier
    return (identity.login or "").lower() == identifier


def access_for(
    identity: Identity | None, owner: tuple[str, str], delegates: Iterable[Delegate]
) -> str | None:
    """Return OWNER, CO_OWNER, DELEGATE or None."""
    if identity is None:
        return None
    if identity.key == owner:
        return OWNER
    for delegate in delegates:
        if matches(identity, delegate.provider, delegate.identifier):
            return CO_OWNER if delegate.role == CO_OWNER_ROLE else DELEGATE
    return None
