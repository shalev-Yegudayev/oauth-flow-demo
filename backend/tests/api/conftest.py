"""Fixtures for API integration tests.

Builds a FastAPI test app with state injected directly (no lifespan) so tests
run without a real Redis server or network. GitHub HTTP calls are intercepted
by a per-test respx.mock context (autouse); the internal service uses its
mock transport.
"""

from datetime import UTC, datetime

import fakeredis
import fakeredis.aioredis as fakeredis_aio
import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Isolated Redis per test
# ---------------------------------------------------------------------------


@pytest.fixture
async def api_redis():
    server = fakeredis.FakeServer()
    r = fakeredis_aio.FakeRedis(server=server)
    await r.flushall()
    yield r
    await r.aclose()


# ---------------------------------------------------------------------------
# respx global mock — blocks all httpx calls, tests register routes as needed
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def github_mock():
    """Block all external httpx calls. Tests configure routes they need."""
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


# ---------------------------------------------------------------------------
# FastAPI test app — state injected, no lifespan
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_app(api_redis, test_settings, cipher, monkeypatch):
    """FastAPI app with all dependencies injected as test doubles."""
    import config
    import deps

    monkeypatch.setattr(config, "get_settings", lambda: test_settings)
    monkeypatch.setattr(deps, "get_settings", lambda: test_settings)

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.core.exceptions import (
        OAuthError,
        oauth_error_handler,
        unhandled_error_handler,
    )
    from app.core.rate_limit import limiter as _route_limiter
    from app.routes.auth import router as auth_router
    from app.routes.profile import router as profile_router
    from app.services.internal_service import (
        InternalServiceClient,
        mock_transport_handler,
    )
    from app.services.session_store import SessionStore

    app = FastAPI(title="Test OAuth")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[test_settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.limiter = _route_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(OAuthError, oauth_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(auth_router)
    app.include_router(profile_router)

    provider_http = httpx.AsyncClient()
    internal_http = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_transport_handler)
    )

    app.state.redis = api_redis
    app.state.cipher = cipher
    app.state.store = SessionStore(
        api_redis,
        test_settings.SESSION_TTL_SECONDS,
        test_settings.STATE_TTL_SECONDS,
        test_settings.USER_PROFILE_TTL_SECONDS,
    )
    app.state.provider_http = provider_http
    app.state.internal_client = InternalServiceClient(internal_http, test_settings)

    yield app

    await provider_http.aclose()
    await internal_http.aclose()


# ---------------------------------------------------------------------------
# HTTP client against the test app
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
        follow_redirects=False,
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Shortcut accessors
# ---------------------------------------------------------------------------


@pytest.fixture
def store(test_app):
    return test_app.state.store


# ---------------------------------------------------------------------------
# Pre-authenticated client (session already seeded + cookie set)
# ---------------------------------------------------------------------------


@pytest.fixture
async def authed_client(client, store, cipher):
    """client with a valid session seeded in the store and cookie pre-set."""
    from app.models.session import SessionRecord

    session_id = "api-authed-sess"
    record = SessionRecord(
        session_id=session_id,
        provider="github",
        provider_user_id="42",
        encrypted_access_token=cipher.encrypt("gho_api_test"),
        encrypted_refresh_token=cipher.encrypt("gho_api_refresh"),
        token_expires_at=None,
        scope="public_repo read:user",
        created_at=datetime.now(UTC),
        last_refreshed_at=None,
    )
    await store.create_session(record)
    client.cookies.set("session_id", session_id)
    return client
