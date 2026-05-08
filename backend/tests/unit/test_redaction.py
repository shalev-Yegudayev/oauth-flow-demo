"""Tests for the _redact helper in app/core/exceptions.py."""

import pytest

from app.core.exceptions import _redact


class TestRedactSensitiveNames:
    @pytest.mark.parametrize(
        "name",
        [
            "token",
            "access_token",
            "refresh_token",
            "id_token",
            "TOKEN",
            "Authorization",
            "authorization",
            "AUTHORIZATION",
            "secret",
            "client_secret",
            "SECRET",
            "api_key",
            "api-key",
            "apikey",
            "API_KEY",
            "code_verifier",
            "CODE_VERIFIER",
            "refresh",
            "REFRESH",
            "x-api-key",
        ],
    )
    def test_sensitive_name_is_redacted(self, name):
        assert _redact(name) == "[REDACTED]"


class TestRedactSafeNames:
    @pytest.mark.parametrize(
        "name",
        [
            "username",
            "email",
            "user_id",
            "provider",
            "scope",
            "state",
            "redirect_uri",
            "code",           # the auth code itself is not matched (no keyword hit)
            "grant_type",
            "client_id",
            "expires_in",
            "created_at",
            "role",
            "tier",
        ],
    )
    def test_safe_name_is_passed_through(self, name):
        assert _redact(name) == name


class TestRedactCaseSensitivity:
    def test_mixed_case_token(self):
        assert _redact("Token") == "[REDACTED]"

    def test_mixed_case_authorization(self):
        assert _redact("Authorization") == "[REDACTED]"

    def test_mixed_case_secret(self):
        assert _redact("Client_Secret") == "[REDACTED]"


class TestRedactSubstringMatching:
    def test_token_as_substring(self):
        # "access_token" contains "token" → must be redacted.
        assert _redact("access_token") == "[REDACTED]"

    def test_secret_as_substring(self):
        assert _redact("github_client_secret") == "[REDACTED]"

    def test_refresh_as_substring(self):
        assert _redact("refresh_token_value") == "[REDACTED]"
