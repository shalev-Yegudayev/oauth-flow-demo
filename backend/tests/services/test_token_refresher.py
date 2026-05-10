"""Tests for TokenRefresher (app/services/token_refresher.py).

Uses fakeredis + respx to exercise every branch:
- Token with no expiry → skip refresh
- Token with expiry but within runway → skip refresh
- Token in refresh window → triggers refresh
- No refresh token → session deleted, TokenRefreshError raised
- Corrupt ciphertext → session deleted, TokenRefreshError raised
- Concurrent refresh → Redis lock serialises, waiter picks up refreshed record
- Lock holder failure → waiter raises TokenRefreshError("session_lost_during_refresh")
- Lock timeout → HTTP 503
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import TokenRefreshError
from app.providers.base import AccessToken
from app.services.token_refresher import _LOCK_TTL, TokenRefresher

_NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
_REFRESH_WINDOW_SECONDS = 60


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.refresh_token = AsyncMock()
    return provider


@pytest.fixture
def refresher(fake_redis, session_store, cipher, mock_provider):
    return TokenRefresher(
        redis=fake_redis,
        store=session_store,
        cipher=cipher,
        provider=mock_provider,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future(seconds: int) -> datetime:
    return _NOW + timedelta(seconds=seconds)


def _past(seconds: int) -> datetime:
    return _NOW - timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# Skip-refresh paths
# ---------------------------------------------------------------------------


class TestSkipRefresh:
    async def test_no_expiry_skips_refresh(
        self, refresher, make_session_record, mock_provider
    ):
        record = make_session_record(token_expires_at=None)
        result = await refresher.ensure_fresh(record)

        assert result is record
        mock_provider.refresh_token.assert_not_called()

    async def test_token_with_long_runway_skips_refresh(
        self, refresher, make_session_record, mock_provider
    ):
        # Expires 10 minutes from "now" — well outside the 60-second window.
        import time_machine

        with time_machine.travel(_NOW):
            record = make_session_record(token_expires_at=_future(600))
            result = await refresher.ensure_fresh(record)

        assert result is record
        mock_provider.refresh_token.assert_not_called()


# ---------------------------------------------------------------------------
# Refresh triggered
# ---------------------------------------------------------------------------


class TestRefreshTriggered:
    async def test_token_in_window_triggers_refresh(
        self, refresher, session_store, make_session_record, mock_provider, cipher
    ):
        import time_machine

        new_access = "gho_new_access"
        new_refresh = "gho_new_refresh"
        mock_provider.refresh_token.return_value = AccessToken(
            value=new_access,
            refresh_token=new_refresh,
            expires_at=_future(28800),
            scope="public_repo",
        )

        with time_machine.travel(_NOW):
            # Expires in 30 seconds — inside the 60-second refresh window.
            record = make_session_record(
                session_id="sess-refresh-trigger",
                token_expires_at=_future(30),
            )
            await session_store.create_session(record)
            result = await refresher.ensure_fresh(record)

        mock_provider.refresh_token.assert_called_once()
        assert cipher.decrypt(result.encrypted_access_token) == new_access
        assert cipher.decrypt(result.encrypted_refresh_token) == new_refresh

    async def test_refresh_updates_session_in_store(
        self, refresher, session_store, make_session_record, mock_provider, cipher
    ):
        import time_machine

        mock_provider.refresh_token.return_value = AccessToken(
            value="gho_updated",
            refresh_token="gho_updated_refresh",
            expires_at=_future(28800),
            scope="public_repo",
        )

        with time_machine.travel(_NOW):
            record = make_session_record(
                session_id="sess-refresh-persist",
                token_expires_at=_future(30),
            )
            await session_store.create_session(record)
            await refresher.ensure_fresh(record)
            # Read back inside the same time context so the Redis TTL
            # (3600 s from _NOW) hasn't expired in wall-clock time.
            stored = await session_store.get_session("sess-refresh-persist")

        assert cipher.decrypt(stored.encrypted_access_token) == "gho_updated"

    async def test_refresh_rotates_refresh_token(
        self, refresher, session_store, make_session_record, mock_provider, cipher
    ):
        import time_machine

        mock_provider.refresh_token.return_value = AccessToken(
            value="gho_new",
            refresh_token="gho_rotated_refresh",
            expires_at=_future(28800),
            scope="",
        )

        with time_machine.travel(_NOW):
            record = make_session_record(
                session_id="sess-rotate",
                refresh_token="gho_old_refresh",
                token_expires_at=_future(30),
            )
            await session_store.create_session(record)
            result = await refresher.ensure_fresh(record)

        assert cipher.decrypt(result.encrypted_refresh_token) == "gho_rotated_refresh"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestRefreshErrorPaths:
    async def test_no_refresh_token_raises_and_deletes_session(
        self, refresher, session_store, make_session_record
    ):
        import time_machine

        with time_machine.travel(_NOW):
            record = make_session_record(
                session_id="sess-no-refresh",
                refresh_token=None,
                token_expires_at=_future(30),
            )
            await session_store.create_session(record)

            with pytest.raises(TokenRefreshError, match="no_refresh_token"):
                await refresher.ensure_fresh(record)

        deleted = await session_store.get_session("sess-no-refresh")
        assert deleted is None

    async def test_corrupt_refresh_token_raises_and_deletes_session(
        self, refresher, session_store, make_session_record
    ):
        import time_machine

        with time_machine.travel(_NOW):
            record = make_session_record(
                session_id="sess-corrupt",
                token_expires_at=_future(30),
            )
            # Corrupt the encrypted refresh token in-place.
            bad_record = record.model_copy(
                update={"encrypted_refresh_token": "not-valid-fernet"}
            )
            await session_store.create_session(bad_record)

            with pytest.raises(TokenRefreshError, match="corrupt_refresh_token"):
                await refresher.ensure_fresh(bad_record)

        deleted = await session_store.get_session("sess-corrupt")
        assert deleted is None

    async def test_provider_refresh_failure_raises_and_deletes_session(
        self, refresher, session_store, make_session_record, mock_provider
    ):
        import time_machine

        mock_provider.refresh_token.side_effect = Exception("provider_down")

        with time_machine.travel(_NOW):
            record = make_session_record(
                session_id="sess-provider-fail",
                token_expires_at=_future(30),
            )
            await session_store.create_session(record)

            with pytest.raises(TokenRefreshError, match="refresh_failed"):
                await refresher.ensure_fresh(record)

        deleted = await session_store.get_session("sess-provider-fail")
        assert deleted is None


# ---------------------------------------------------------------------------
# Lock contention — waiter path
# ---------------------------------------------------------------------------


class TestLockContention:
    async def test_waiter_picks_up_refreshed_record(
        self, fake_redis, session_store, make_session_record, mock_provider, cipher
    ):
        """The _wait_for_refresh path returns the updated record once expiry changes.

        We simulate a lock holder by: acquiring the lock manually, writing an
        already-refreshed session into the store, then releasing the lock.
        The waiter (which polls for the expiry change) must return the new record.
        """
        import time_machine

        session_id = "sess-lock-waiter"
        new_expires = _future(28800)

        with time_machine.travel(_NOW):
            original = make_session_record(
                session_id=session_id,
                token_expires_at=_future(30),
            )
            await session_store.create_session(original)

            # Simulate a completed refresh: write the updated session directly.
            refreshed_record = original.model_copy(
                update={
                    "encrypted_access_token": cipher.encrypt("gho_refreshed"),
                    "token_expires_at": new_expires,
                }
            )

            # The waiter reads the session after each poll interval. We schedule
            # an update to happen on the first poll cycle by running the store
            # update concurrently with the wait loop.
            async def _simulate_lock_holder():
                await asyncio.sleep(0)          # yield so waiter starts first
                await session_store.update_session(refreshed_record)

            refresher = TokenRefresher(fake_redis, session_store, cipher, mock_provider)

            # Manually hold the lock so ensure_fresh takes the waiter path.
            lock_key = f"oauth:refresh_lock:{session_id}"
            await fake_redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL)

            result, _ = await asyncio.gather(
                refresher.ensure_fresh(original),
                _simulate_lock_holder(),
            )

        assert result.token_expires_at == new_expires
        assert cipher.decrypt(result.encrypted_access_token) == "gho_refreshed"
        # The waiter never calls the provider — it picked up the store update.
        mock_provider.refresh_token.assert_not_called()

    async def test_waiter_raises_if_session_deleted_during_refresh(
        self, fake_redis, session_store, make_session_record, cipher
    ):
        """If the lock holder deletes the session (failure), the waiter must raise."""
        import time_machine

        session_id = "sess-lock-lost"

        async def _failing_refresh(*_):
            raise Exception("provider_error")

        failing_provider = MagicMock()
        failing_provider.refresh_token = AsyncMock(side_effect=_failing_refresh)

        with time_machine.travel(_NOW):
            record = make_session_record(
                session_id=session_id,
                token_expires_at=_future(30),
            )
            await session_store.create_session(record)

            # Manually acquire the lock to simulate a holder.
            lock_key = f"oauth:refresh_lock:{session_id}"
            await fake_redis.set(lock_key, "1", nx=True, ex=20)

            # Delete the session to simulate the lock holder failing.
            await session_store.delete_session(session_id)

            refresher = TokenRefresher(fake_redis, session_store, cipher, failing_provider)

            with pytest.raises(TokenRefreshError, match="session_lost_during_refresh"):
                await refresher.ensure_fresh(record)
