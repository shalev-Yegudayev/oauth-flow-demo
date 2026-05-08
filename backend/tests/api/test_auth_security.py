"""API integration tests — adversarial callback cases.

Covers:
- Missing code / state params
- Unknown or replayed state
- Provider mismatch between URL and stored state
- Provider error query param (user denied access)
- Insufficient OAuth scope
"""

from datetime import UTC, datetime

from app.models.session import StateRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_state(
    store,
    state_key: str = "test-state-sec",
    provider: str = "github",
    verifier: str = "test-verifier",
):
    await store.put_state(
        state_key,
        StateRecord(
            provider=provider,
            code_verifier=verifier,
            created_at=datetime.now(UTC),
        ),
    )


# ---------------------------------------------------------------------------
# Missing / malformed parameters
# ---------------------------------------------------------------------------


class TestMissingParams:
    async def test_missing_code_returns_400(self, client, store):
        await _seed_state(store)
        response = await client.get(
            "/auth/github/callback?state=test-state-sec"
        )
        assert response.status_code == 400

    async def test_missing_state_returns_400(self, client):
        response = await client.get(
            "/auth/github/callback?code=some-code"
        )
        assert response.status_code == 400

    async def test_missing_both_returns_400(self, client):
        response = await client.get("/auth/github/callback")
        assert response.status_code == 400

    async def test_provider_error_param_returns_400(self, client):
        response = await client.get(
            "/auth/github/callback?error=access_denied"
        )
        assert response.status_code == 400

    async def test_error_response_has_error_key(self, client):
        response = await client.get("/auth/github/callback")
        body = response.json()
        assert "error" in body


# ---------------------------------------------------------------------------
# State validation
# ---------------------------------------------------------------------------


class TestStateValidation:
    async def test_unknown_state_returns_400(self, client):
        response = await client.get(
            "/auth/github/callback?code=abc&state=nonexistent-state"
        )
        assert response.status_code == 400

    async def test_unknown_state_error_message(self, client):
        response = await client.get(
            "/auth/github/callback?code=abc&state=ghost-state"
        )
        assert response.json()["error"] == "invalid_or_expired_state"

    async def test_state_replay_second_call_returns_400(
        self, client, store, github_mock, test_settings
    ):
        """State is single-use; the second callback with the same state must fail."""
        await _seed_state(store, state_key="replay-state")
        github_mock.post(test_settings.GITHUB_TOKEN_URL).respond(
            200, json={"access_token": "gho_t", "scope": "public_repo read:user"}
        )
        github_mock.get(f"{test_settings.GITHUB_API_BASE}/user").respond(
            200, json={"id": 99}
        )

        first = await client.get(
            "/auth/github/callback?code=abc&state=replay-state"
        )
        assert first.status_code == 307

        second = await client.get(
            "/auth/github/callback?code=abc&state=replay-state"
        )
        assert second.status_code == 400
        assert second.json()["error"] == "invalid_or_expired_state"

    async def test_provider_mismatch_returns_400(self, client, store):
        """state.provider=other but URL provider is github → 400 provider_mismatch."""
        await _seed_state(store, state_key="mismatch-state", provider="other")
        response = await client.get(
            "/auth/github/callback?code=abc&state=mismatch-state"
        )
        assert response.status_code == 400
        assert response.json()["error"] == "provider_mismatch"


# ---------------------------------------------------------------------------
# Scope enforcement
# ---------------------------------------------------------------------------


class TestScopeEnforcement:
    async def test_insufficient_scope_returns_400(
        self, client, store, github_mock, test_settings
    ):
        """GitHub returns a token missing read:user → handler raises OAuthError."""
        await _seed_state(store, state_key="scope-state")
        github_mock.post(test_settings.GITHUB_TOKEN_URL).respond(
            200, json={"access_token": "gho_narrow", "scope": "public_repo"}
        )

        response = await client.get(
            "/auth/github/callback?code=abc&state=scope-state"
        )
        assert response.status_code == 400
        assert response.json()["error"] == "insufficient_scope"
