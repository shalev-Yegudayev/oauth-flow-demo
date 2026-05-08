from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis

from app.models.session import SessionRecord, StateRecord, UserProfileRecord

_STATE_PREFIX = "oauth:state:"
_SESSION_PREFIX = "oauth:session:"
_PROFILE_PREFIX = "oauth:user:"
_12_HOURS = timedelta(hours=12)

# Atomically GET then DEL a state key in one round-trip.
# Prevents replay races where two concurrent callbacks consume the same state.
_POP_LUA = """
local v = redis.call('GET', KEYS[1])
redis.call('DEL', KEYS[1])
return v
"""


class SessionStore:
    def __init__(
        self,
        redis: aioredis.Redis,
        session_ttl: int,
        state_ttl: int,
        profile_ttl: int,
    ) -> None:
        self._r = redis
        self._session_ttl = session_ttl
        self._state_ttl = state_ttl
        self._profile_ttl = profile_ttl

    # ------------------------------------------------------------------
    # State (CSRF / PKCE — single-use, short TTL)
    # ------------------------------------------------------------------

    async def put_state(self, state: str, record: StateRecord) -> None:
        await self._r.setex(
            f"{_STATE_PREFIX}{state}",
            self._state_ttl,
            record.model_dump_json(),
        )

    async def pop_state(self, state: str) -> StateRecord | None:
        raw: bytes | None = await self._r.eval(_POP_LUA, 1, f"{_STATE_PREFIX}{state}")
        if raw is None:
            return None
        return StateRecord.model_validate_json(raw.decode("utf-8"))

    # ------------------------------------------------------------------
    # Session (auth lifecycle)
    # ------------------------------------------------------------------

    async def create_session(self, record: SessionRecord) -> None:
        await self._r.setex(
            f"{_SESSION_PREFIX}{record.session_id}",
            self._session_ttl,
            record.model_dump_json(),
        )

    async def get_session(self, session_id: str) -> SessionRecord | None:
        raw: bytes | None = await self._r.get(f"{_SESSION_PREFIX}{session_id}")
        if raw is None:
            return None
        record = SessionRecord.model_validate_json(raw.decode("utf-8"))
        # Hard ceiling: reject sessions older than 12 h regardless of sliding TTL.
        if datetime.now(UTC) - record.created_at > _12_HOURS:
            await self.delete_session(session_id)
            return None
        # Sliding TTL: each access resets the expiry so active sessions stay alive.
        await self._r.expire(f"{_SESSION_PREFIX}{session_id}", self._session_ttl)
        return record

    async def update_session(self, record: SessionRecord) -> None:
        await self._r.setex(
            f"{_SESSION_PREFIX}{record.session_id}",
            self._session_ttl,
            record.model_dump_json(),
        )

    async def delete_session(self, session_id: str) -> None:
        await self._r.delete(f"{_SESSION_PREFIX}{session_id}")

    # ------------------------------------------------------------------
    # User profile cache (internal service data — independent TTL)
    # ------------------------------------------------------------------

    async def get_user_profile(self, provider_user_id: str) -> UserProfileRecord | None:
        raw: bytes | None = await self._r.get(f"{_PROFILE_PREFIX}{provider_user_id}")
        if raw is None:
            return None
        return UserProfileRecord.model_validate_json(raw.decode("utf-8"))

    async def set_user_profile(self, record: UserProfileRecord) -> None:
        await self._r.setex(
            f"{_PROFILE_PREFIX}{record.provider_user_id}",
            self._profile_ttl,
            record.model_dump_json(),
        )
