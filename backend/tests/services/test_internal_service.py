"""Tests for InternalServiceClient (app/services/internal_service.py).

The mock transport is deterministic (seeded by user_id) so the same user_id
always returns the same name/tier/role. Tests verify:
- Determinism across calls
- Correct API key validation
- Network errors map to InternalServiceError(503)
- Invalid response JSON maps to InternalServiceError(502)
- Wrong API key returns InternalServiceError(401)
"""

import httpx
import pytest

from app.core.exceptions import InternalServiceError
from app.services.internal_service import InternalServiceClient, mock_transport_handler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_get_settings(test_settings, monkeypatch):
    """Patch config.get_settings so mock_transport_handler sees test values."""
    import config

    monkeypatch.setattr(config, "get_settings", lambda: test_settings)


@pytest.fixture
def internal_client(test_settings):
    """InternalServiceClient using the mock transport (no real network)."""
    transport = httpx.MockTransport(mock_transport_handler)
    http = httpx.AsyncClient(transport=transport)
    return InternalServiceClient(http=http, settings=test_settings)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestMockDeterminism:
    async def test_same_user_id_always_returns_same_name(self, internal_client):
        r1 = await internal_client.get_user("12345")
        r2 = await internal_client.get_user("12345")
        assert r1.user_name == r2.user_name

    async def test_same_user_id_always_returns_same_tier(self, internal_client):
        r1 = await internal_client.get_user("99999")
        r2 = await internal_client.get_user("99999")
        assert r1.tier == r2.tier

    async def test_same_user_id_always_returns_same_role(self, internal_client):
        r1 = await internal_client.get_user("abc123")
        r2 = await internal_client.get_user("abc123")
        assert r1.role == r2.role

    async def test_different_user_ids_may_differ(self, internal_client):
        """Not guaranteed to differ but the seed changes — just check no crash."""
        r1 = await internal_client.get_user("user-alpha")
        r2 = await internal_client.get_user("user-beta")
        assert r1.provider_user_id == "user-alpha"
        assert r2.provider_user_id == "user-beta"

    async def test_provider_user_id_echoed(self, internal_client):
        result = await internal_client.get_user("my-uid")
        assert result.provider_user_id == "my-uid"

    async def test_tier_is_valid_literal(self, internal_client):
        result = await internal_client.get_user("12345")
        assert result.tier in ("Pro", "Basic")

    async def test_role_is_valid_value(self, internal_client):
        result = await internal_client.get_user("12345")
        assert result.role in ("developer", "admin", "analyst", "viewer")


# ---------------------------------------------------------------------------
# Authentication check
# ---------------------------------------------------------------------------


class TestApiKeyValidation:
    async def test_wrong_api_key_raises_internal_service_error(self, test_settings):
        transport = httpx.MockTransport(mock_transport_handler)
        http = httpx.AsyncClient(transport=transport)

        from config import Settings

        bad_settings = Settings.model_validate(
            {**test_settings.model_dump(), "INTERNAL_API_KEY": "wrong-key"}
        )
        client = InternalServiceClient(http=http, settings=bad_settings)

        with pytest.raises(InternalServiceError) as exc_info:
            await client.get_user("12345")
        assert exc_info.value.upstream_status == 401

    async def test_correct_api_key_succeeds(self, internal_client):
        result = await internal_client.get_user("12345")
        assert result is not None


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------


class TestNetworkErrors:
    async def test_request_error_raises_503(self, test_settings):
        """ConnectError (or any RequestError) must map to InternalServiceError(503)."""

        async def _raise(_request):
            raise httpx.ConnectError("connection refused")

        transport = httpx.MockTransport(_raise)
        http = httpx.AsyncClient(transport=transport)
        client = InternalServiceClient(http=http, settings=test_settings)

        with pytest.raises(InternalServiceError) as exc_info:
            await client.get_user("12345")
        assert exc_info.value.upstream_status == 503

    async def test_non_200_status_raises_internal_service_error(self, test_settings):
        """A 500 from the internal service maps to InternalServiceError(500)."""

        def _500(_request):
            return httpx.Response(500, json={"error": "server_error"})

        transport = httpx.MockTransport(_500)
        http = httpx.AsyncClient(transport=transport)
        client = InternalServiceClient(http=http, settings=test_settings)

        with pytest.raises(InternalServiceError) as exc_info:
            await client.get_user("12345")
        assert exc_info.value.upstream_status == 500

    async def test_invalid_json_body_raises_502(self, test_settings):
        """Unparseable JSON from internal service maps to InternalServiceError(502)."""

        def _bad_json(request):
            # Correct API key so auth passes, but body is malformed.
            api_key = test_settings.INTERNAL_API_KEY.get_secret_value()
            if request.headers.get("X-Internal-API-Key") == api_key:
                return httpx.Response(200, json={"totally": "wrong_schema"})
            return httpx.Response(401)

        transport = httpx.MockTransport(_bad_json)
        http = httpx.AsyncClient(transport=transport)
        client = InternalServiceClient(http=http, settings=test_settings)

        with pytest.raises(InternalServiceError) as exc_info:
            await client.get_user("12345")
        assert exc_info.value.upstream_status == 502
