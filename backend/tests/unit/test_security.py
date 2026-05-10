"""Tests for app/core/security.py — PKCE math, state entropy, cookie attributes."""

import base64
import hashlib

from fastapi import Response

from app.core.security import (
    clear_session_cookie,
    compute_code_challenge,
    generate_code_verifier,
    generate_state,
    set_session_cookie,
)


class TestGenerateState:
    def test_returns_string(self):
        assert isinstance(generate_state(), str)

    def test_minimum_entropy(self):
        # 32 random bytes → at least 42 base64url chars (rstrip removes padding).
        assert len(generate_state()) >= 42

    def test_unique_each_call(self):
        states = {generate_state() for _ in range(50)}
        assert len(states) == 50

    def test_url_safe_characters_only(self):
        for _ in range(20):
            state = generate_state()
            # base64url alphabet plus no padding '='
            assert all(
                c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                for c in state
            )


class TestGenerateCodeVerifier:
    def test_returns_string(self):
        assert isinstance(generate_code_verifier(), str)

    def test_minimum_length(self):
        # RFC 7636 §4.1: verifier must be 43–128 chars. 64 random bytes → 85 chars.
        verifier = generate_code_verifier()
        assert 43 <= len(verifier) <= 128

    def test_unique_each_call(self):
        verifiers = {generate_code_verifier() for _ in range(50)}
        assert len(verifiers) == 50

    def test_url_safe_characters_only(self):
        for _ in range(20):
            verifier = generate_code_verifier()
            assert all(
                c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                for c in verifier
            )


class TestComputeCodeChallenge:
    def test_s256_algorithm(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert compute_code_challenge(verifier) == expected

    def test_different_verifiers_produce_different_challenges(self):
        v1 = generate_code_verifier()
        v2 = generate_code_verifier()
        assert compute_code_challenge(v1) != compute_code_challenge(v2)

    def test_challenge_is_deterministic(self):
        verifier = generate_code_verifier()
        assert compute_code_challenge(verifier) == compute_code_challenge(verifier)

    def test_challenge_no_padding(self):
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        assert "=" not in challenge

    def test_challenge_url_safe(self):
        for _ in range(20):
            verifier = generate_code_verifier()
            challenge = compute_code_challenge(verifier)
            assert all(
                c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                for c in challenge
            )

    def test_verifier_challenge_pair_validates(self):
        """The challenge must equal BASE64URL(SHA256(verifier)) — the PKCE S256 spec."""
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert challenge == expected


class TestSetSessionCookie:
    def _get_cookie_header(self, response: Response) -> str:
        headers = response.headers.getlist("set-cookie")
        assert headers, "No Set-Cookie header found"
        return headers[0]

    def test_session_id_value_set(self, test_settings):
        resp = Response()
        set_session_cookie(resp, "sess-xyz", test_settings)
        header = self._get_cookie_header(resp)
        assert "sess-xyz" in header

    def test_httponly_present(self, test_settings):
        resp = Response()
        set_session_cookie(resp, "sess-xyz", test_settings)
        header = self._get_cookie_header(resp).lower()
        assert "httponly" in header

    def test_samesite_lax_in_dev(self, test_settings):
        assert test_settings.ENV == "dev"
        resp = Response()
        set_session_cookie(resp, "sess-xyz", test_settings)
        header = self._get_cookie_header(resp).lower()
        assert "samesite=lax" in header

    def test_samesite_lax_in_prod(self, test_settings):
        from config import Settings

        prod_settings = Settings.model_validate(
            {**test_settings.model_dump(), "ENV": "production"}
        )
        resp = Response()
        set_session_cookie(resp, "sess-xyz", prod_settings)
        header = self._get_cookie_header(resp).lower()
        assert "samesite=lax" in header

    def test_not_secure_in_dev(self, test_settings):
        # ENV=dev → Secure flag must be absent.
        assert test_settings.ENV == "dev"
        resp = Response()
        set_session_cookie(resp, "sess-xyz", test_settings)
        header = self._get_cookie_header(resp).lower()
        # "secure" could appear in samesite=... but not as a standalone flag
        parts = [p.strip() for p in header.split(";")]
        assert "secure" not in parts

    def test_secure_in_prod(self, test_settings):
        from config import Settings

        prod_settings = Settings.model_validate(
            {**test_settings.model_dump(), "ENV": "production"}
        )
        resp = Response()
        set_session_cookie(resp, "sess-xyz", prod_settings)
        header = self._get_cookie_header(resp).lower()
        parts = [p.strip() for p in header.split(";")]
        assert "secure" in parts

    def test_max_age_set(self, test_settings):
        resp = Response()
        set_session_cookie(resp, "sess-xyz", test_settings)
        header = self._get_cookie_header(resp).lower()
        assert "max-age=" in header

    def test_path_is_root(self, test_settings):
        resp = Response()
        set_session_cookie(resp, "sess-xyz", test_settings)
        header = self._get_cookie_header(resp).lower()
        assert "path=/" in header


class TestClearSessionCookie:
    def test_max_age_is_zero(self, test_settings):
        resp = Response()
        clear_session_cookie(resp, test_settings)
        header = resp.headers.getlist("set-cookie")[0].lower()
        assert "max-age=0" in header

    def test_value_is_empty(self, test_settings):
        resp = Response()
        clear_session_cookie(resp, test_settings)
        header = resp.headers.getlist("set-cookie")[0]
        # Starlette may quote the empty value as "" or leave it bare — either is valid.
        value_part = header.split(";")[0]
        assert value_part in ("session_id=", 'session_id=""')
