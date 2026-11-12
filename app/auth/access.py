"""Who may do what in a room: the owner, a delegate, or nobody special.

Delegates match on a Google account's verified email or a GitHub login, never on
display name, which anyone can change.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.auth.identity import Identity

if TYPE_CHECKING:
    from app.store.rooms import Delegate

OWNER = "owner"
DELEGATE = "delegate"


def access_for(
    identity: Identity | None, owner: tuple[str, str], delegates: Iterable[Delegate]
) -> str | None:
    """Return OWNER, DELEGATE or None. The owner matches on provider and stable subject ID."""
    if identity is None:
        return None
    if identity.key == owner:
        return OWNER
    for delegate in delegates:
        if delegate.provider != identity.provider:
            continue
        if identity.provider == "google" and identity.email == delegate.identifier:
            return DELEGATE
        if identity.provider == "github" and (identity.login or "").lower() == delegate.identifier:
            return DELEGATE
    return None
