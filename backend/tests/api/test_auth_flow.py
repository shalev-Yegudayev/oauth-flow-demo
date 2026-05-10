"""API integration tests — happy-path auth flow.

Covers:
- GET  /auth/{provider}           → 307 redirect to provider authorization URL
- GET  /auth/{provider}/callback  → 307 redirect to frontend + session cookie
- POST /auth/logout               → 204, cookie cleared, session deleted
"""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from app.models.session import StateRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_state(store, state_key: str = "test-state-abc", verifier: str = "test-verifier"):
    return store.put_state(
        state_key,
        StateRecord(
            provider="github",
            code_verifier=verifier,
            created_at=datetime.now(UTC),
        ),
    )


def _mock_github_token(github_mock, test_settings, *, scope: str = "public_repo,read:user"):
    github_mock.post(test_settings.GITHUB_TOKEN_URL).respond(
        200,
        json={"access_token": "gho_callback_test", "scope": scope},
    )


def _mock_github_user(github_mock, test_settings, *, user_id: int = 42):
    github_mock.get(f"{test_settings.GITHUB_API_BASE}/user").respond(
        200, json={"id": user_id}
    )


# ---------------------------------------------------------------------------
# GET /auth/{provider}
# ---------------------------------------------------------------------------


class TestStartOAuth:
    async def test_returns_307(self, client):
        response = await client.get("/auth/github")
        assert response.status_code == 307

    async def test_location_starts_with_authorize_url(self, client, test_settings):
        response = await client.get("/auth/github")
        location = response.headers["location"]
        assert location.startswith(test_settings.GITHUB_AUTHORIZE_URL)

    async def test_location_contains_state_param(self, client):
        response = await client.get("/auth/github")
        qs = parse_qs(urlparse(response.headers["location"]).query)
        assert "state" in qs
        assert len(qs["state"][0]) >= 42  # 32 random bytes → ≥42 chars base64url

    async def test_location_contains_pkce_s256(self, client):
        response = await client.get("/auth/github")
        qs = parse_qs(urlparse(response.headers["location"]).query)
        assert qs.get("code_challenge_method") == ["S256"]
        assert "code_challenge" in qs

    async def test_state_is_stored_in_redis(self, client, store):
        response = await client.get("/auth/github")
        qs = parse_qs(urlparse(response.headers["location"]).query)
        state_key = qs["state"][0]

        record = await store.pop_state(state_key)
        assert record is not None
        assert record.provider == "github"


# ---------------------------------------------------------------------------
# GET /auth/{provider}/callback
# ---------------------------------------------------------------------------


class TestCallback:
    async def test_success_returns_307(
        self, client, store, github_mock, test_settings
    ):
        await _seed_state(store)
        _mock_github_token(github_mock, test_settings)
        _mock_github_user(github_mock, test_settings)

        response = await client.get(
            "/auth/github/callback?code=test-code&state=test-state-abc"
        )
        assert response.status_code == 307

    async def test_success_redirects_to_post_login(
        self, client, store, github_mock, test_settings
    ):
        await _seed_state(store)
        _mock_github_token(github_mock, test_settings)
        _mock_github_user(github_mock, test_settings)

        response = await client.get(
            "/auth/github/callback?code=test-code&state=test-state-abc"
        )
        assert response.headers["location"] == test_settings.POST_LOGIN_REDIRECT

    async def test_success_sets_session_cookie(
        self, client, store, github_mock, test_settings
    ):
        await _seed_state(store)
        _mock_github_token(github_mock, test_settings)
        _mock_github_user(github_mock, test_settings)

        response = await client.get(
            "/auth/github/callback?code=test-code&state=test-state-abc"
        )
        assert "session_id" in response.cookies

    async def test_success_creates_session_in_store(
        self, client, store, github_mock, test_settings, cipher
    ):
        await _seed_state(store)
        _mock_github_token(github_mock, test_settings)
        _mock_github_user(github_mock, test_settings)

        response = await client.get(
            "/auth/github/callback?code=test-code&state=test-state-abc"
        )
        session_id = response.cookies["session_id"]
        record = await store.get_session(session_id)

        assert record is not None
        assert record.provider == "github"
        assert record.provider_user_id == "42"
        assert cipher.decrypt(record.encrypted_access_token) == "gho_callback_test"


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    async def test_without_cookie_returns_204(self, client):
        response = await client.post("/auth/logout")
        assert response.status_code == 204

    async def test_with_valid_session_returns_204(self, authed_client):
        response = await authed_client.post("/auth/logout")
        assert response.status_code == 204

    async def test_with_valid_session_clears_cookie(self, authed_client):
        response = await authed_client.post("/auth/logout")
        set_cookie = response.headers.get("set-cookie", "")
        assert "max-age=0" in set_cookie.lower()

    async def test_with_valid_session_deletes_from_store(self, authed_client, store):
        await authed_client.post("/auth/logout")
        record = await store.get_session("api-authed-sess")
        assert record is None
