"""Tests for pure parsing helpers in app/providers/github.py."""

from datetime import UTC, datetime, timedelta

import pytest

from app.providers.github import GithubProvider, _next_link


class TestParseTokenResponse:
    """Tests for GithubProvider._parse_token_response (static method)."""

    def test_parses_access_token(self):
        payload = {"access_token": "gho_abc", "scope": "public_repo"}
        result = GithubProvider._parse_token_response(payload)
        assert result.value == "gho_abc"

    def test_parses_scope_comma_separated(self):
        # GitHub returns scopes comma-separated; parser must normalize to spaces.
        payload = {"access_token": "gho_abc", "scope": "public_repo,read:user"}
        result = GithubProvider._parse_token_response(payload)
        assert result.scope == "public_repo read:user"

    def test_parses_scope_space_separated(self):
        payload = {"access_token": "gho_abc", "scope": "public_repo read:user"}
        result = GithubProvider._parse_token_response(payload)
        assert result.scope == "public_repo read:user"

    def test_empty_scope_defaults_to_empty_string(self):
        payload = {"access_token": "gho_abc"}
        result = GithubProvider._parse_token_response(payload)
        assert result.scope == ""

    def test_parses_refresh_token(self):
        payload = {
            "access_token": "gho_abc",
            "refresh_token": "gho_refresh_xyz",
            "scope": "",
        }
        result = GithubProvider._parse_token_response(payload)
        assert result.refresh_token == "gho_refresh_xyz"

    def test_refresh_token_absent_is_none(self):
        payload = {"access_token": "gho_abc", "scope": ""}
        result = GithubProvider._parse_token_response(payload)
        assert result.refresh_token is None

    def test_expires_in_produces_future_datetime(self):
        before = datetime.now(UTC)
        payload = {"access_token": "gho_abc", "scope": "", "expires_in": 28800}
        result = GithubProvider._parse_token_response(payload)
        after = datetime.now(UTC)

        assert result.expires_at is not None
        expected_min = before + timedelta(seconds=28800)
        expected_max = after + timedelta(seconds=28800)
        assert expected_min <= result.expires_at <= expected_max

    def test_no_expires_in_produces_none(self):
        payload = {"access_token": "gho_abc", "scope": ""}
        result = GithubProvider._parse_token_response(payload)
        assert result.expires_at is None

    def test_expires_in_string_is_cast_to_int(self):
        payload = {"access_token": "gho_abc", "scope": "", "expires_in": "3600"}
        result = GithubProvider._parse_token_response(payload)
        assert result.expires_at is not None


class TestNextLink:
    """Tests for _next_link — RFC 5988 Link header parser."""

    def test_single_next_link(self):
        header = '<https://api.github.com/user/repos?page=2>; rel="next"'
        assert _next_link(header) == "https://api.github.com/user/repos?page=2"

    def test_next_link_among_multiple_rels(self):
        header = (
            '<https://api.github.com/user/repos?page=1>; rel="prev", '
            '<https://api.github.com/user/repos?page=3>; rel="next", '
            '<https://api.github.com/user/repos?page=5>; rel="last"'
        )
        assert _next_link(header) == "https://api.github.com/user/repos?page=3"

    def test_no_next_rel_returns_none(self):
        header = '<https://api.github.com/user/repos?page=1>; rel="prev"'
        assert _next_link(header) is None

    def test_empty_header_returns_none(self):
        assert _next_link("") is None

    def test_last_page_no_next(self):
        header = (
            '<https://api.github.com/user/repos?page=4>; rel="prev", '
            '<https://api.github.com/user/repos?page=5>; rel="last"'
        )
        assert _next_link(header) is None

    def test_only_next_rel(self):
        header = '<https://example.com/repos?page=2>; rel="next"'
        assert _next_link(header) == "https://example.com/repos?page=2"

    def test_link_with_extra_whitespace(self):
        # GitHub includes spaces around the semicolon.
        header = '  <https://api.github.com/repos?page=2> ; rel="next"  '
        # Our implementation splits on comma then splits on semicolon — spaces are stripped.
        result = _next_link(header)
        assert result == "https://api.github.com/repos?page=2"

    def test_first_page_link_header(self):
        header = (
            '<https://api.github.com/user/repos?page=2>; rel="next", '
            '<https://api.github.com/user/repos?page=5>; rel="last"'
        )
        assert _next_link(header) == "https://api.github.com/user/repos?page=2"
