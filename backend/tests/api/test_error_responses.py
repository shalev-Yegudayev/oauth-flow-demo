"""API integration tests — error response shape and secret non-disclosure.

Covers:
- OAuth callback errors redirect to /login?error=<code> (never raw JSON)
- Error redirect URLs never contain raw token values or credentials
- Non-callback errors (e.g. /profile 401) still return structured JSON
- Unknown routes return 404
- Content-Type is application/json for JSON error responses
"""


# ---------------------------------------------------------------------------
# Callback error shape — redirects, not JSON
# ---------------------------------------------------------------------------


class TestCallbackErrorShape:
    async def test_callback_missing_params_redirects(self, client, test_settings):
        response = await client.get("/auth/github/callback")
        assert response.status_code == 302
        assert response.headers["location"].startswith(
            f"{test_settings.FRONTEND_ORIGIN}/login?error="
        )

    async def test_callback_invalid_state_redirects(self, client, test_settings):
        response = await client.get(
            "/auth/github/callback?code=abc&state=ghost"
        )
        assert response.status_code == 302
        assert "invalid_or_expired_state" in response.headers["location"]


# ---------------------------------------------------------------------------
# Non-callback JSON errors still have correct shape
# ---------------------------------------------------------------------------


class TestJsonErrorShape:
    async def test_no_session_returns_401_with_detail(self, client):
        """get_authenticated_session raises HTTPException (not OAuthError) → detail key."""
        response = await client.get("/profile")
        assert response.status_code == 401
        assert "detail" in response.json()

    async def test_no_session_content_type_json(self, client):
        response = await client.get("/profile")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Secret non-disclosure
# ---------------------------------------------------------------------------


class TestSecretNonDisclosure:
    async def test_invalid_state_does_not_leak_code_in_redirect(self, client):
        """The redirect URL must not echo back the code parameter."""
        response = await client.get(
            "/auth/github/callback?code=super_secret_code&state=ghost"
        )
        location = response.headers["location"]
        assert "super_secret_code" not in location

    async def test_provider_error_redirect_does_not_expose_raw_param(self, client):
        """The redirect URL preserves the provider error value but must not add secrets."""
        response = await client.get(
            "/auth/github/callback?error=access_denied"
        )
        assert response.status_code == 302
        location = response.headers["location"]
        assert "access_denied" in location
        assert "access_token" not in location


# ---------------------------------------------------------------------------
# Unknown routes
# ---------------------------------------------------------------------------


class TestUnknownRoutes:
    async def test_unknown_route_returns_404(self, client):
        response = await client.get("/does-not-exist")
        assert response.status_code == 404

    async def test_get_on_logout_returns_404(self, client):
        # GET /auth/logout matches /{provider} with provider="logout" (not registered)
        response = await client.get("/auth/logout")
        assert response.status_code == 404
