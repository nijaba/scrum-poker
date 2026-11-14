"""Configuration from environment variables. See .env.example.

APP_BASE_URL            public address, for OAuth callbacks; https:// except on localhost
SESSION_SECRET          signs the session cookie; required outside localhost
ROOM_CREATOR_ALLOWLIST  who may create rooms (see Allowlist)
DATABASE_PATH           the SQLite file holding room definitions
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
ATLASSIAN_CLIENT_ID, ATLASSIAN_CLIENT_SECRET   Jira Cloud (OAuth 2.0 3LO app)
TOKEN_ENCRYPTION_KEY    Fernet key for stored Jira refresh tokens; required outside localhost
SCRUM_POKER_FAKE_SSO    1 to sign in through the built-in fake provider (localhost only)
SCRUM_POKER_FAKE_JIRA   1 to use the built-in fake Jira Cloud (localhost only)
"""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from app.auth.identity import Identity
from app.jira.crypto import new_key, valid_key

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_DATABASE = "./data/scrum-poker.sqlite3"
DEFAULT_FORWARDED_ALLOW_IPS = "127.0.0.1"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
FAKE_SSO_PATH = "/_fake-sso"
FAKE_JIRA_PATH = "/_fake-jira"

# Granular scopes, per Atlassian's Jira Software OpenAPI spec. See design.md, "Jira Cloud".
ATLASSIAN_SCOPES = (
    "read:board-scope:jira-software",
    "read:board-scope.admin:jira-software",
    "read:project:jira",
    "read:issue-details:jira",
    "write:issue:jira-software",
    "read:me",
    "offline_access",
)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+$")
_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


class ConfigError(ValueError):
    """The configuration cannot be used. The message says which variable to fix."""


def is_local_host(host: str | None) -> bool:
    host = (host or "").lower().strip("[]")
    return host in LOCAL_HOSTS or host.endswith(".localhost")


@dataclass(frozen=True)
class Allowlist:
    """Who may create rooms.

    Comma-separated entries:
      *                          anyone signed in
      ana@example.com            a Google account, by verified email
      github:ana-dev             a GitHub account, by login
      google-domain:example.com  any account in that Google Workspace (the `hd` claim)
      github-org:acme            any member of that GitHub organisation
    """

    anyone: bool = False
    emails: frozenset[str] = frozenset()
    logins: frozenset[str] = frozenset()
    domains: frozenset[str] = frozenset()
    orgs: frozenset[str] = frozenset()

    @staticmethod
    def parse(text: str) -> Allowlist:
        anyone = False
        emails, logins, domains, orgs = set(), set(), set(), set()
        for raw in text.split(","):
            entry = raw.strip()
            if not entry:
                continue
            lowered = entry.lower()
            prefix, _, rest = lowered.partition(":")
            if entry == "*":
                anyone = True
            elif prefix == "github" and _LOGIN.match(rest):
                logins.add(rest)
            elif prefix == "github-org" and _LOGIN.match(rest):
                orgs.add(rest)
            elif prefix == "google-domain" and _DOMAIN.match(rest):
                domains.add(rest)
            elif ":" not in entry and _EMAIL.match(lowered):
                emails.add(lowered)
            else:
                raise ConfigError(f"ROOM_CREATOR_ALLOWLIST: cannot read the entry {entry!r}.")
        return Allowlist(
            anyone, frozenset(emails), frozenset(logins), frozenset(domains), frozenset(orgs)
        )

    @property
    def github_orgs(self) -> tuple[str, ...]:
        """Orgs whose membership must be checked at GitHub sign-in."""
        return tuple(sorted(self.orgs))

    def allows(self, identity: Identity | None) -> bool:
        if identity is None:
            return False
        if self.anyone:
            return True
        if identity.provider == "google":
            return (identity.email or "") in self.emails or (identity.domain or "") in self.domains
        if identity.provider == "github":
            login = (identity.login or "").lower()
            return login in self.logins or any(o in self.orgs for o in identity.orgs)
        return False


@dataclass(frozen=True)
class ProviderConfig:
    name: str  # "google" or "github"
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str
    callback_url: str
    api_url: str = ""  # GitHub API root, for org membership


@dataclass(frozen=True)
class AtlassianConfig:
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    api_url: str  # api.atlassian.com: accessible resources, /me, and /ex/jira/{cloudId}
    callback_url: str
    scope: str = " ".join(ATLASSIAN_SCOPES)


def atlassian_config(
    base_url: str, client_id: str, client_secret: str, fake_root: str | None = None
) -> AtlassianConfig:
    callback = f"{base_url}/auth/atlassian/callback"
    if fake_root:
        return AtlassianConfig(
            client_id,
            client_secret,
            f"{fake_root}/auth/authorize",
            f"{fake_root}/auth/oauth/token",
            f"{fake_root}/api",
            callback,
        )
    return AtlassianConfig(
        client_id,
        client_secret,
        "https://auth.atlassian.com/authorize",
        "https://auth.atlassian.com/oauth/token",
        "https://api.atlassian.com",
        callback,
    )


@dataclass(frozen=True)
class Settings:
    base_url: str = DEFAULT_BASE_URL
    session_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    allowlist: Allowlist = field(default_factory=Allowlist)
    database_path: Path = Path(DEFAULT_DATABASE)
    providers: Mapping[str, ProviderConfig] = field(default_factory=dict)
    fake_sso: bool = False
    token_key: str = field(default_factory=new_key)
    atlassian: AtlassianConfig | None = None
    fake_jira: bool = False
    # Demo rooms: a private room per visitor, with bots and a made-up backlog.
    demo_rooms: bool = False
    # Proxies whose X-Forwarded-Proto and X-Forwarded-For the app believes; "*" for any.
    forwarded_allow_ips: str = DEFAULT_FORWARDED_ALLOW_IPS

    @property
    def is_local(self) -> bool:
        return is_local_host(urlsplit(self.base_url).hostname)

    @property
    def secure_cookies(self) -> bool:
        return not self.is_local

    @property
    def origin(self) -> str:
        parts = urlsplit(self.base_url)
        return f"{parts.scheme}://{parts.netloc}"

    @staticmethod
    def from_env(env: Mapping[str, str]) -> Settings:
        base_url = (env.get("APP_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ConfigError("APP_BASE_URL must be an http(s) address.")
        local = is_local_host(parts.hostname)
        if not local and parts.scheme != "https":
            raise ConfigError("APP_BASE_URL must use https:// outside localhost.")

        secret = env.get("SESSION_SECRET") or ""
        if not secret or secret == "change-me":
            if not local:
                raise ConfigError("SESSION_SECRET is required outside localhost.")
            secret = secrets.token_urlsafe(32)
            log.warning("SESSION_SECRET is not set: using a random one; sign-ins end on restart.")
        elif len(secret) < 32:
            raise ConfigError("SESSION_SECRET must be at least 32 characters.")

        fake = env.get("SCRUM_POKER_FAKE_SSO", "").strip() in ("1", "true", "yes")
        if fake and not local:
            raise ConfigError("The fake SSO provider only runs on localhost.")

        allowlist = Allowlist.parse(env.get("ROOM_CREATOR_ALLOWLIST", ""))
        providers = _providers(env, base_url, allowlist, fake)

        fake_jira = env.get("SCRUM_POKER_FAKE_JIRA", "").strip() in ("1", "true", "yes")
        if fake_jira and not local:
            raise ConfigError("The fake Jira only runs on localhost.")
        atlassian = None
        if fake_jira:
            atlassian = atlassian_config(base_url, "fake", "fake", base_url + FAKE_JIRA_PATH)
        else:
            cid = env.get("ATLASSIAN_CLIENT_ID", "").strip()
            secret_ = env.get("ATLASSIAN_CLIENT_SECRET", "").strip()
            if cid and secret_:
                atlassian = atlassian_config(base_url, cid, secret_)
            elif cid or secret_:
                raise ConfigError("Set both ATLASSIAN_CLIENT_ID and ATLASSIAN_CLIENT_SECRET.")

        token_key = env.get("TOKEN_ENCRYPTION_KEY", "").strip()
        if token_key and not valid_key(token_key):
            raise ConfigError(
                "TOKEN_ENCRYPTION_KEY must be a Fernet key: 32 url-safe base64 bytes. Generate one"
                " with: python -c 'from cryptography.fernet import Fernet;"
                " print(Fernet.generate_key().decode())'"
            )
        if not token_key:
            if atlassian is not None and not local:
                raise ConfigError("TOKEN_ENCRYPTION_KEY is required outside localhost.")
            token_key = new_key()
            log.warning(
                "TOKEN_ENCRYPTION_KEY is not set: using a random one;"
                " Jira connections end on restart."
            )
        return Settings(
            base_url=base_url,
            session_secret=secret,
            allowlist=allowlist,
            database_path=Path(env.get("DATABASE_PATH") or DEFAULT_DATABASE),
            providers=providers,
            fake_sso=fake,
            token_key=token_key,
            atlassian=atlassian,
            fake_jira=fake_jira,
            demo_rooms=env.get("DEMO_ROOMS", "").strip() in ("1", "true", "yes"),
            forwarded_allow_ips=(
                env.get("FORWARDED_ALLOW_IPS") or DEFAULT_FORWARDED_ALLOW_IPS
            ).strip(),
        )


def provider_config(
    name: str,
    base_url: str,
    client_id: str,
    client_secret: str,
    *,
    github_orgs: bool = False,
    fake_root: str | None = None,
) -> ProviderConfig:
    """Endpoints for a provider: the real ones, or the fake provider's under `fake_root`."""
    callback = f"{base_url}/auth/{name}/callback"
    if name == "google":
        if fake_root:
            urls = (f"{fake_root}/google/authorize", f"{fake_root}/google/token")
            userinfo = f"{fake_root}/google/userinfo"
        else:
            urls = (
                "https://accounts.google.com/o/oauth2/v2/auth",
                "https://oauth2.googleapis.com/token",
            )
            userinfo = "https://openidconnect.googleapis.com/v1/userinfo"
        return ProviderConfig(
            "google", client_id, client_secret, *urls, userinfo, "openid email profile", callback
        )
    if name == "github":
        api = f"{fake_root}/github/api" if fake_root else "https://api.github.com"
        if fake_root:
            urls = (f"{fake_root}/github/authorize", f"{fake_root}/github/token")
        else:
            urls = (
                "https://github.com/login/oauth/authorize",
                "https://github.com/login/oauth/access_token",
            )
        scope = "read:user read:org" if github_orgs else "read:user"
        return ProviderConfig(
            "github", client_id, client_secret, *urls, f"{api}/user", scope, callback, api
        )
    raise ConfigError(f"Unknown sign-in provider {name!r}.")


def _providers(
    env: Mapping[str, str], base_url: str, allowlist: Allowlist, fake: bool
) -> dict[str, ProviderConfig]:
    orgs = bool(allowlist.github_orgs)
    if fake:
        root = base_url + FAKE_SSO_PATH
        return {
            name: provider_config(name, base_url, "fake", "fake", github_orgs=orgs, fake_root=root)
            for name in ("google", "github")
        }
    found = {}
    for name in ("google", "github"):
        cid = env.get(f"{name.upper()}_CLIENT_ID", "").strip()
        secret = env.get(f"{name.upper()}_CLIENT_SECRET", "").strip()
        if cid and secret:
            found[name] = provider_config(name, base_url, cid, secret, github_orgs=orgs)
        elif cid or secret:
            raise ConfigError(
                f"Set both {name.upper()}_CLIENT_ID and {name.upper()}_CLIENT_SECRET."
            )
    return found
