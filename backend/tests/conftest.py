"""
Shared fixtures for all test layers.

Settings are overridden at import time via monkeypatching get_settings so no
real .env file is needed. Redis is provided by fakeredis (in-process) so the
test suite runs without a running Redis instance.
"""

from datetime import UTC, datetime

import fakeredis
import fakeredis.aioredis as fakeredis_aio
import pytest
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Settings override — must happen before any app module is imported in tests
# ---------------------------------------------------------------------------

TEST_FERNET_KEY: str = Fernet.generate_key().decode()

TEST_SETTINGS_KWARGS: dict = {
    "GITHUB_CLIENT_ID": "test-client-id",
    "GITHUB_CLIENT_SECRET": "test-client-secret",
    "GITHUB_REDIRECT_URI": "http://localhost:8000/auth/github/callback",
    "GITHUB_AUTHORIZE_URL": "https://github-mock.internal/login/oauth/authorize",
    "GITHUB_TOKEN_URL": "https://github-mock.internal/login/oauth/access_token",
    "GITHUB_API_BASE": "https://github-mock.internal/api",
    "INTERNAL_SERVICE_URL": "http://internal-mock.internal",
    "INTERNAL_API_KEY": "test-internal-key",
    "INTERNAL_SERVICE_MOCK": True,
    "REDIS_URL": "redis://localhost:6379/15",
    "SESSION_SECRET": TEST_FERNET_KEY,
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "POST_LOGIN_REDIRECT": "http://localhost:5173/dashboard",
    "ENV": "dev",
    "SESSION_TTL_SECONDS": 3600,
    "STATE_TTL_SECONDS": 300,
    "USER_PROFILE_TTL_SECONDS": 3600,
}


@pytest.fixture(scope="session")
def test_settings():
    """Return a Settings instance populated with test values (no .env read)."""
    from config import Settings

    return Settings.model_validate(TEST_SETTINGS_KWARGS)


# ---------------------------------------------------------------------------
# Fake Redis — shared across a module, flushed between tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def fake_redis():
    """Async fakeredis instance with Lua scripting enabled, flushed before each test."""
    server = fakeredis.FakeServer()
    r = fakeredis_aio.FakeRedis(server=server)
    await r.flushall()
    yield r
    await r.aclose()


# ---------------------------------------------------------------------------
# SessionStore backed by fake Redis
# ---------------------------------------------------------------------------


@pytest.fixture
def session_store(fake_redis, test_settings):
    from app.services.session_store import SessionStore

    return SessionStore(
        redis=fake_redis,
        session_ttl=test_settings.SESSION_TTL_SECONDS,
        state_ttl=test_settings.STATE_TTL_SECONDS,
        profile_ttl=test_settings.USER_PROFILE_TTL_SECONDS,
    )


# ---------------------------------------------------------------------------
# TokenCipher backed by test key
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def cipher(test_settings):
    from app.core.crypto import TokenCipher

    return TokenCipher([TEST_FERNET_KEY])


# ---------------------------------------------------------------------------
# Minimal StateRecord / SessionRecord factories
# ---------------------------------------------------------------------------


@pytest.fixture
def make_state_record():
    from app.models.session import StateRecord

    def _make(
        provider: str = "github", code_verifier: str = "verifier-abc"
    ) -> StateRecord:
        return StateRecord(
            provider=provider,
            code_verifier=code_verifier,
            created_at=datetime.now(UTC),
        )

    return _make


@pytest.fixture
def make_session_record(cipher):
    from app.models.session import SessionRecord

    def _make(
        session_id: str = "sess-001",
        provider_user_id: str = "12345",
        access_token: str = "gho_access",
        refresh_token: str | None = "gho_refresh",
        token_expires_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> SessionRecord:
        return SessionRecord(
            session_id=session_id,
            provider="github",
            provider_user_id=provider_user_id,
            encrypted_access_token=cipher.encrypt(access_token),
            encrypted_refresh_token=(
                cipher.encrypt(refresh_token) if refresh_token else None
            ),
            token_expires_at=token_expires_at,
            scope="public_repo read:user",
            created_at=created_at or datetime.now(UTC),
            last_refreshed_at=None,
        )

    return _make
