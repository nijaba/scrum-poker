"""Configuration, the owner allowlist and delegate matching, at Unit level.

The flows these rules gate (AR-01 to AR-13) are proved in test_auth.py and test_rooms_api.py.
"""

import pytest

from app.auth.access import OWNER, access_for
from app.auth.identity import Identity
from app.config import Allowlist, ConfigError, Settings
from app.store.rooms import Delegate

ANA_G = Identity("google", "g-1", "Ana", email="ana@example.com", domain="example.com")
GMAIL = Identity("google", "g-2", "Gus", email="gus@gmail.com")
OCTO = Identity("github", "1001", "Octo", login="Octo-Dev", orgs=("acme",))
LONER = Identity("github", "1002", "Lone", login="lone")


def test_empty_allowlist_allows_nobody():
    allow = Allowlist.parse("")
    assert not any(allow.allows(i) for i in (ANA_G, GMAIL, OCTO, LONER))


def test_star_allows_anyone_signed_in():
    assert all(Allowlist.parse("*").allows(i) for i in (ANA_G, GMAIL, OCTO, LONER))


def test_emails_and_github_logins():
    allow = Allowlist.parse(" Gus@Gmail.com , github:octo-dev ")
    assert allow.allows(GMAIL)
    assert allow.allows(OCTO)  # logins compare without case
    assert not allow.allows(ANA_G)
    assert not allow.allows(LONER)


def test_providers_do_not_cross():
    # A GitHub account whose login looks like an email does not match an email entry.
    sneaky = Identity("github", "9", "S", login="gus@gmail.com")
    assert not Allowlist.parse("gus@gmail.com").allows(sneaky)
    assert not Allowlist.parse("github:ana").allows(Identity("google", "g", "A", email="ana"))


def test_google_workspace_domain_uses_the_hd_claim():
    allow = Allowlist.parse("google-domain:example.com")
    assert allow.allows(ANA_G)
    # A personal Google account with an example.com address has no hosted domain.
    personal = Identity("google", "g-3", "P", email="pat@example.com", domain=None)
    assert not allow.allows(personal)


def test_github_org():
    allow = Allowlist.parse("github-org:ACME")
    assert allow.allows(OCTO)
    assert not allow.allows(LONER)
    assert allow.github_orgs == ("acme",)


@pytest.mark.parametrize("text", ["slack:ana", "github:", "google-domain:", "a b@c"])
def test_unknown_entries_are_rejected(text):
    with pytest.raises(ConfigError):
        Allowlist.parse(text)


def test_settings_from_env_on_localhost_generates_a_secret(caplog):
    settings = Settings.from_env({})
    assert settings.base_url == "http://localhost:8000"
    assert len(settings.session_secret) >= 32
    assert settings.is_local
    assert "SESSION_SECRET" in caplog.text


def test_settings_outside_localhost_need_https_and_a_secret():
    with pytest.raises(ConfigError, match="https"):
        Settings.from_env({"APP_BASE_URL": "http://poker.example.com", "SESSION_SECRET": "x" * 32})
    with pytest.raises(ConfigError, match="SESSION_SECRET"):
        Settings.from_env({"APP_BASE_URL": "https://poker.example.com"})
    settings = Settings.from_env(
        {"APP_BASE_URL": "https://poker.example.com/", "SESSION_SECRET": "x" * 32}
    )
    assert settings.base_url == "https://poker.example.com"
    assert not settings.is_local


def test_fake_sso_is_refused_outside_localhost():
    env = {
        "APP_BASE_URL": "https://poker.example.com",
        "SESSION_SECRET": "x" * 32,
        "SCRUM_POKER_FAKE_SSO": "1",
    }
    with pytest.raises(ConfigError, match="fake"):
        Settings.from_env(env)


def test_providers_are_configured_from_client_ids():
    settings = Settings.from_env(
        {
            "GOOGLE_CLIENT_ID": "gid",
            "GOOGLE_CLIENT_SECRET": "gs",
            "ROOM_CREATOR_ALLOWLIST": "github-org:acme",
        }
    )
    assert set(settings.providers) == {"google"}
    assert settings.providers["google"].callback_url == "http://localhost:8000/auth/google/callback"

    gh = Settings.from_env(
        {
            "GITHUB_CLIENT_ID": "id",
            "GITHUB_CLIENT_SECRET": "s",
            "ROOM_CREATOR_ALLOWLIST": "github-org:acme",
        }
    )
    assert "read:org" in gh.providers["github"].scope  # needed to see org membership


def test_fake_sso_configures_both_providers_against_itself():
    settings = Settings.from_env({"SCRUM_POKER_FAKE_SSO": "1"})
    assert set(settings.providers) == {"google", "github"}
    assert settings.providers["github"].authorize_url.startswith(
        "http://localhost:8000/_fake-sso/github/"
    )


def test_delegates_match_on_verified_email_or_github_login():
    delegates = [Delegate("google", "ana@example.com"), Delegate("github", "octo-dev")]
    owner = ("google", "g-9")

    assert access_for(ANA_G, owner, delegates) == "delegate"
    assert access_for(OCTO, owner, delegates) == "delegate"
    assert access_for(LONER, owner, delegates) is None
    assert access_for(None, owner, delegates) is None
    assert access_for(Identity("google", "g-9", "Own", email="o@x.com"), owner, delegates) == OWNER


def test_display_name_never_matches():
    delegates = [Delegate("github", "octo-dev")]
    impostor = Identity("github", "77", "octo-dev", login="someone-else")
    assert access_for(impostor, ("google", "g-9"), delegates) is None


def test_identity_round_trips():
    assert Identity.from_dict(OCTO.to_dict()) == OCTO
    assert Identity.from_dict({"provider": "slack"}) is None
    assert OCTO.label == "Octo-Dev"
    assert ANA_G.label == "ana@example.com"
