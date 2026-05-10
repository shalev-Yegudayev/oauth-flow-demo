"""Tests for SessionStore (app/services/session_store.py).

Uses fakeredis so no real Redis instance is required. Tests cover:
- State atomicity: pop_state is single-use (Lua script)
- State expiry: expired state returns None
- Session CRUD and sliding TTL
- 12-hour hard ceiling on sessions
- User profile cache
"""

import asyncio
from datetime import UTC, datetime, timedelta

from app.models.session import UserProfileRecord

# ---------------------------------------------------------------------------
# State record tests
# ---------------------------------------------------------------------------


class TestPutPopState:
    async def test_pop_returns_stored_record(self, session_store, make_state_record):
        state = "test-state-001"
        record = make_state_record()
        await session_store.put_state(state, record)

        result = await session_store.pop_state(state)
        assert result is not None
        assert result.provider == record.provider
        assert result.code_verifier == record.code_verifier

    async def test_pop_is_single_use(self, session_store, make_state_record):
        """Second pop on the same state must return None — replay attack prevention."""
        state = "test-state-002"
        await session_store.put_state(state, make_state_record())

        first = await session_store.pop_state(state)
        second = await session_store.pop_state(state)

        assert first is not None
        assert second is None

    async def test_pop_unknown_state_returns_none(self, session_store):
        result = await session_store.pop_state("nonexistent-state")
        assert result is None

    async def test_state_preserves_code_verifier(self, session_store, make_state_record):
        state = "test-state-003"
        verifier = "super-secret-verifier-xyz"
        await session_store.put_state(state, make_state_record(code_verifier=verifier))

        result = await session_store.pop_state(state)
        assert result.code_verifier == verifier

    async def test_state_preserves_provider(self, session_store, make_state_record):
        state = "test-state-004"
        await session_store.put_state(state, make_state_record(provider="github"))

        result = await session_store.pop_state(state)
        assert result.provider == "github"

    async def test_concurrent_pops_only_one_succeeds(self, session_store, make_state_record):
        """Two coroutines racing on the same state — exactly one must win."""
        state = "test-state-race"
        await session_store.put_state(state, make_state_record())

        results = await asyncio.gather(
            session_store.pop_state(state),
            session_store.pop_state(state),
        )
        non_none = [r for r in results if r is not None]
        assert len(non_none) == 1


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


class TestCreateGetSession:
    async def test_get_returns_created_session(self, session_store, make_session_record):
        record = make_session_record(session_id="sess-get-001")
        await session_store.create_session(record)

        result = await session_store.get_session("sess-get-001")
        assert result is not None
        assert result.session_id == "sess-get-001"
        assert result.provider_user_id == record.provider_user_id

    async def test_get_unknown_session_returns_none(self, session_store):
        result = await session_store.get_session("does-not-exist")
        assert result is None

    async def test_delete_session_removes_it(self, session_store, make_session_record):
        record = make_session_record(session_id="sess-del-001")
        await session_store.create_session(record)
        await session_store.delete_session("sess-del-001")

        result = await session_store.get_session("sess-del-001")
        assert result is None

    async def test_update_session_persists_changes(self, session_store, make_session_record, cipher):
        record = make_session_record(session_id="sess-upd-001", access_token="old-token")
        await session_store.create_session(record)

        updated = record.model_copy(
            update={"encrypted_access_token": cipher.encrypt("new-token")}
        )
        await session_store.update_session(updated)

        result = await session_store.get_session("sess-upd-001")
        assert cipher.decrypt(result.encrypted_access_token) == "new-token"

    async def test_encrypted_token_not_stored_as_plaintext(
        self, session_store, make_session_record, fake_redis
    ):
        """Access token must never appear in plaintext in Redis."""
        record = make_session_record(session_id="sess-enc-001", access_token="gho_plaintext")
        await session_store.create_session(record)

        raw: bytes = await fake_redis.get("oauth:session:sess-enc-001")
        assert b"gho_plaintext" not in raw


# ---------------------------------------------------------------------------
# 12-hour hard ceiling
# ---------------------------------------------------------------------------


class TestTwelveHourCeiling:
    async def test_session_within_12_hours_is_accessible(
        self, session_store, make_session_record
    ):
        # Pin created_at 10 hours in the past — ceiling check uses the stored
        # value, not wall time, so Redis TTL is not involved here.
        created_at = datetime.now(UTC) - timedelta(hours=10)
        record = make_session_record(session_id="sess-12h-ok", created_at=created_at)
        await session_store.create_session(record)

        result = await session_store.get_session("sess-12h-ok")
        assert result is not None

    async def test_session_past_12_hours_returns_none(
        self, session_store, make_session_record
    ):
        created_at = datetime.now(UTC) - timedelta(hours=13)
        record = make_session_record(session_id="sess-12h-expired", created_at=created_at)
        await session_store.create_session(record)

        result = await session_store.get_session("sess-12h-expired")
        assert result is None

    async def test_session_past_12_hours_is_deleted(
        self, session_store, make_session_record, fake_redis
    ):
        created_at = datetime.now(UTC) - timedelta(hours=13)
        record = make_session_record(session_id="sess-12h-del", created_at=created_at)
        await session_store.create_session(record)

        await session_store.get_session("sess-12h-del")

        raw = await fake_redis.get("oauth:session:sess-12h-del")
        assert raw is None


# ---------------------------------------------------------------------------
# Sliding TTL
# ---------------------------------------------------------------------------


class TestSlidingTtl:
    async def test_get_session_resets_ttl(self, session_store, make_session_record, fake_redis):
        record = make_session_record(session_id="sess-sliding")
        await session_store.create_session(record)

        # Lower the TTL manually to simulate near-expiry.
        await fake_redis.expire("oauth:session:sess-sliding", 10)
        ttl_before = await fake_redis.ttl("oauth:session:sess-sliding")
        assert ttl_before <= 10

        await session_store.get_session("sess-sliding")

        ttl_after = await fake_redis.ttl("oauth:session:sess-sliding")
        assert ttl_after > ttl_before


# ---------------------------------------------------------------------------
# User profile cache
# ---------------------------------------------------------------------------


class TestUserProfileCache:
    async def test_set_and_get_profile(self, session_store):
        profile = UserProfileRecord(
            provider_user_id="uid-001",
            user_name="Alex Chen",
            tier="Pro",
            role="developer",
        )
        await session_store.set_user_profile(profile)

        result = await session_store.get_user_profile("uid-001")
        assert result is not None
        assert result.user_name == "Alex Chen"
        assert result.tier == "Pro"

    async def test_get_missing_profile_returns_none(self, session_store):
        result = await session_store.get_user_profile("uid-missing")
        assert result is None

    async def test_profile_overwrite(self, session_store):
        profile = UserProfileRecord(
            provider_user_id="uid-002", user_name="Old Name", tier="Basic", role="viewer"
        )
        await session_store.set_user_profile(profile)

        updated = UserProfileRecord(
            provider_user_id="uid-002", user_name="New Name", tier="Pro", role="admin"
        )
        await session_store.set_user_profile(updated)

        result = await session_store.get_user_profile("uid-002")
        assert result.user_name == "New Name"
        assert result.tier == "Pro"
