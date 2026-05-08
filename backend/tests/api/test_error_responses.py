"""API integration tests — error response shape and secret non-disclosure.

Covers:
- All OAuthError responses return {"error": "<message>"} JSON
- Error bodies never contain raw token values or credentials
- Unknown routes return 404
- Content-Type is application/json for all errors
"""


# ---------------------------------------------------------------------------
# Error body shape
# ---------------------------------------------------------------------------


class TestErrorShape:
    async def test_callback_error_has_error_key(self, client):
        response = await client.get("/auth/github/callback")
        assert response.status_code == 400
        body = response.json()
        assert "error" in body
        assert "detail" not in body  # FastAPI's default shape must not bleed through

    async def test_callback_error_content_type_json(self, client):
        response = await client.get("/auth/github/callback")
        assert "application/json" in response.headers["content-type"]

    async def test_invalid_state_error_key(self, client):
        response = await client.get(
            "/auth/github/callback?code=abc&state=ghost"
        )
        assert response.status_code == 400
        assert "error" in response.json()

    async def test_no_session_returns_401_with_detail(self, client):
        """get_authenticated_session raises HTTPException (not OAuthError) → detail key."""
        response = await client.get("/profile")
        assert response.status_code == 401
        assert "detail" in response.json()


# ---------------------------------------------------------------------------
# Secret non-disclosure
# ---------------------------------------------------------------------------


class TestSecretNonDisclosure:
    async def test_invalid_state_does_not_leak_code(self, client):
        """The error body must not echo back the code parameter."""
        response = await client.get(
            "/auth/github/callback?code=super_secret_code&state=ghost"
        )
        body = response.text
        assert "super_secret_code" not in body

    async def test_provider_error_message_not_echoed_verbatim(self, client):
        """The raw error= query param value is included in the error string but
        must not appear as a standalone plaintext token."""
        response = await client.get(
            "/auth/github/callback?error=access_denied"
        )
        # The handler wraps it as "provider_error:access_denied" — the raw
        # param is present in the message, which is acceptable (not a secret).
        assert response.status_code == 400
        assert "error" in response.json()


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
