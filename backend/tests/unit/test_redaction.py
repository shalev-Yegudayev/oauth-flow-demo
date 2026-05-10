import logging

import pytest

from app.core.security import REDACT_RE, RedactingFilter


class TestRedactReSensitiveNames:
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
    def test_sensitive_name_matches(self, name):
        assert REDACT_RE.search(name) is not None


class TestRedactReSafeNames:
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
            "code",
            "grant_type",
            "client_id",
            "expires_in",
            "created_at",
            "role",
            "tier",
        ],
    )
    def test_safe_name_does_not_match(self, name):
        assert REDACT_RE.search(name) is None


class TestRedactingFilter:
    def _make_record(self, msg: str) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg=msg,
            args=(), exc_info=None,
        )
        return record

    def test_sensitive_keyword_in_message_is_replaced(self):
        f = RedactingFilter()
        record = self._make_record("exchanging token abc123")
        f.filter(record)
        assert record.msg == "exchanging [REDACTED] abc123"

    def test_safe_message_is_unchanged(self):
        f = RedactingFilter()
        record = self._make_record("user logged in as alice")
        f.filter(record)
        assert record.msg == "user logged in as alice"

    def test_multiple_sensitive_keywords_all_replaced(self):
        f = RedactingFilter()
        record = self._make_record("token exchanged, secret stored")
        f.filter(record)
        assert record.msg == "[REDACTED] exchanged, [REDACTED] stored"

    def test_filter_always_returns_true(self):
        f = RedactingFilter()
        record = self._make_record("token xyz")
        assert f.filter(record) is True

    def test_case_insensitive_replacement(self):
        f = RedactingFilter()
        record = self._make_record("Authorization header present")
        f.filter(record)
        assert record.msg == "[REDACTED] header present"
