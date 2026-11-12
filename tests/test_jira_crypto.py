"""Refresh-token encryption, at Unit level. JC-13 checks the SQLite file end to end."""

import pytest
from cryptography.fernet import Fernet

from app.config import ConfigError, Settings
from app.jira.crypto import TokenCipher


def test_round_trip_and_ciphertext_hides_the_token():
    cipher = TokenCipher(Fernet.generate_key().decode())
    sealed = cipher.seal("refresh-secret")

    assert "refresh-secret" not in sealed
    assert cipher.open(sealed) == "refresh-secret"
    assert cipher.seal("refresh-secret") != sealed  # fresh IV every time


def test_a_different_key_cannot_open_it():
    sealed = TokenCipher(Fernet.generate_key().decode()).seal("x")
    assert TokenCipher(Fernet.generate_key().decode()).open(sealed) is None
    assert TokenCipher(Fernet.generate_key().decode()).open("garbage") is None


def test_key_is_required_outside_localhost_when_atlassian_is_configured():
    env = {
        "APP_BASE_URL": "https://poker.example.com",
        "SESSION_SECRET": "x" * 32,
        "ATLASSIAN_CLIENT_ID": "id",
        "ATLASSIAN_CLIENT_SECRET": "s",
    }
    with pytest.raises(ConfigError, match="TOKEN_ENCRYPTION_KEY"):
        Settings.from_env(env)
    with pytest.raises(ConfigError, match="TOKEN_ENCRYPTION_KEY"):
        Settings.from_env({**env, "TOKEN_ENCRYPTION_KEY": "not-a-fernet-key"})
    key = Fernet.generate_key().decode()
    settings = Settings.from_env({**env, "TOKEN_ENCRYPTION_KEY": key})
    assert settings.token_key == key
    assert settings.atlassian.callback_url == "https://poker.example.com/auth/atlassian/callback"
    assert settings.atlassian.authorize_url == "https://auth.atlassian.com/authorize"


def test_localhost_generates_a_key_with_a_warning(caplog):
    settings = Settings.from_env({})
    assert TokenCipher(settings.token_key).open(TokenCipher(settings.token_key).seal("t")) == "t"
    assert "TOKEN_ENCRYPTION_KEY" in caplog.text


def test_atlassian_scopes_are_the_seven_in_the_design():
    settings = Settings.from_env({"ATLASSIAN_CLIENT_ID": "id", "ATLASSIAN_CLIENT_SECRET": "s"})
    assert settings.atlassian.scope.split() == [
        "read:board-scope:jira-software",
        "read:board-scope.admin:jira-software",
        "read:project:jira",
        "read:issue-details:jira",
        "write:issue:jira-software",
        "read:me",
        "offline_access",
    ]


def test_fake_jira_points_at_itself_and_only_on_localhost():
    settings = Settings.from_env({"SCRUM_POKER_FAKE_JIRA": "1"})
    assert settings.atlassian.api_url == "http://localhost:8000/_fake-jira/api"
    with pytest.raises(ConfigError, match="fake"):
        Settings.from_env(
            {
                "APP_BASE_URL": "https://poker.example.com",
                "SESSION_SECRET": "x" * 32,
                "SCRUM_POKER_FAKE_JIRA": "1",
            }
        )
