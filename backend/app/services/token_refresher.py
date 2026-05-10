from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import HTTPException

from app.core.crypto import InvalidToken, TokenCipher
from app.core.exceptions import TokenRefreshError
from app.models.session import SessionRecord
from app.providers.base import OAuthProvider
from app.services.session_store import SessionStore

logger = logging.getLogger(__name__)

_REFRESH_WINDOW = timedelta(seconds=60)
_LOCK_TTL = 20
_LOCK_POLL_INTERVAL = 0.2
_LOCK_POLL_TIMEOUT = 5.0


class TokenRefresher:
    def __init__(
        self,
        redis: aioredis.Redis,
        store: SessionStore,
        cipher: TokenCipher,
        provider: OAuthProvider,
    ) -> None:
        self._r = redis
        self._store = store
        self._cipher = cipher
        self._provider = provider

    async def ensure_fresh(self, record: SessionRecord) -> SessionRecord:
        # Provider doesn't issue expiring tokens; nothing to refresh.
        if record.token_expires_at is None:
            return record
        # Token still has enough runway — skip refresh until inside the window.
        if record.token_expires_at - datetime.now(UTC) > _REFRESH_WINDOW:
            return record
        # Token is expiring but no refresh token was issued; unrecoverable.
        if record.encrypted_refresh_token is None:
            await self._store.delete_session(record.session_id)
            raise TokenRefreshError("no_refresh_token")

        lock_key = f"oauth:refresh_lock:{record.session_id}"
        acquired = await self._r.set(lock_key, "1", nx=True, ex=_LOCK_TTL)

        if not acquired:
            return await self._wait_for_refresh(record)

        try:
            return await self._do_refresh(record)
        finally:
            await self._r.delete(lock_key)

    async def _do_refresh(self, record: SessionRecord) -> SessionRecord:
        try:
            plaintext_refresh = self._cipher.decrypt(record.encrypted_refresh_token)
        except InvalidToken as exc:
            await self._store.delete_session(record.session_id)
            raise TokenRefreshError("corrupt_refresh_token") from exc

        try:
            new_token = await asyncio.wait_for(
                self._provider.refresh_token(plaintext_refresh),
                timeout=8.0,
            )
        except Exception as exc:
            await self._store.delete_session(record.session_id)
            raise TokenRefreshError("refresh_failed") from exc

        updated = record.model_copy(
            update={
                "encrypted_access_token": self._cipher.encrypt(new_token.value),
                "encrypted_refresh_token": (
                    self._cipher.encrypt(new_token.refresh_token)
                    if new_token.refresh_token
                    else None
                ),
                "token_expires_at": new_token.expires_at,
                "last_refreshed_at": datetime.now(UTC),
            }
        )
        await self._store.update_session(updated)
        return updated

    async def _wait_for_refresh(self, record: SessionRecord) -> SessionRecord:
        # Another coroutine holds the refresh lock; poll until done or timeout.
        elapsed = 0.0
        while elapsed < _LOCK_POLL_TIMEOUT:
            await asyncio.sleep(_LOCK_POLL_INTERVAL)
            elapsed += _LOCK_POLL_INTERVAL
            refreshed = await self._store.get_session(record.session_id)

            # Lock holder deleted the session on failure; propagate the error.
            if refreshed is None:
                raise TokenRefreshError("session_lost_during_refresh")
            # Expiry changed — lock holder completed the refresh successfully.
            if refreshed.token_expires_at != record.token_expires_at:
                return refreshed

        # Lock holder didn't finish within the timeout; tell client to retry.
        raise HTTPException(status_code=503, headers={"Retry-After": "1"})
