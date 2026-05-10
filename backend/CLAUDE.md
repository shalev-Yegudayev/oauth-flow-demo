# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role

FastAPI backend: OAuth broker, session manager, and profile aggregator. The frontend never sees an access token — this service is the only party that holds OAuth credentials, speaks to GitHub, and calls the internal mock service.

## Commands

```powershell
.\venv\Scripts\Activate.ps1          # activate virtualenv
pip install -r requirements.txt      # install runtime deps
pip install -r requirements-test.txt # install test deps (includes runtime)
uvicorn main:app --reload            # dev server on http://localhost:8000
ruff check .                         # lint
ruff format .                        # format
```

### Tests

```powershell
pytest                                        # run all tests
pytest tests/unit/test_crypto.py -k "rotation" # run single test by name
pytest -x                                     # stop on first failure
pytest --cov --cov-fail-under=90              # with coverage (fails below 90%)
```

Test stack: `pytest-asyncio` (asyncio_mode=auto), `respx` for mocking `httpx`, `fakeredis` for Redis, `time-machine` for time travel.

Tests are self-contained — no `.env` or running Redis needed. `tests/conftest.py` monkeypatches `get_settings` before any app module loads.

**Test layers and key fixtures:**

| Layer | Path | Notes |
|---|---|---|
| Unit | `tests/unit/` | Pure logic; uses `cipher`, `make_state_record`, `make_session_record` from root conftest |
| Services | `tests/services/` | Uses `session_store` and `fake_redis` fixtures (fakeredis, no HTTP) |
| API | `tests/api/` | Full request/response; `client` is unauthenticated, `authed_client` has a seeded session cookie |

`github_mock` (autouse in `tests/api/`) blocks all `httpx` calls — register only the routes a test needs via `respx`.

When adding a new `Settings` field, also add it to `TEST_SETTINGS_KWARGS` in `tests/conftest.py`.

### Redis (required for dev)

```bash
docker run -d --name oauth-redis -p 6379:6379 redis:7-alpine
```

## Module map

```
backend/
├── main.py        # FastAPI app factory, lifespan (Redis + httpx), CORS, slowapi, log redaction
├── deps.py        # DI providers: get_redis, get_http_client, get_session_store,
│                  #               get_provider, get_authenticated_session
├── config.py      # Pydantic Settings — all secrets/TTLs loaded from .env
└── app/
    ├── core/      # exceptions.py, crypto.py, security.py, rate_limit.py
    ├── models/    # session.py (StateRecord, SessionRecord, UserProfileRecord)
    │              # profile.py (UnifiedProfile, UserSummary DTOs)
    ├── providers/ # base.py (OAuthProvider ABC), github.py, __init__.py (registry)
    ├── services/  # session_store.py, internal_service.py, token_refresher.py
    └── routes/    # auth.py, profile.py
```

## Architecture

### Session & token security

- Session cookie: `HttpOnly`, `SameSite=Strict`, `Secure` in production. The browser holds only an opaque session ID. (Lax would also work for the OAuth callback chain, but the assignment never relies on a cross-site GET hitting the backend — Strict eliminates that surface entirely.)
- Access tokens are Fernet-encrypted (`app/core/crypto.py`). `TokenCipher` supports key rotation via a comma-separated `SESSION_SECRET` list — retired keys stay in the fallback list so live sessions survive a key rollover.
- Redis state records use a short TTL (~5 min) for CSRF protection; session records use a longer TTL with sliding expiry and a **12-hour hard ceiling** enforced at read time.
- `session_store.py` uses Lua scripts for atomic Redis operations (e.g., `pop_state` is GET+DEL in a single script to prevent state replay).

### Provider abstraction

`OAuthProvider[T]` (`app/providers/base.py`) is a Generic ABC defining the full lifecycle: `authorization_url`, `exchange_code`, `refresh_token`, `fetch_user_id`, `revoke_token`, `fetch_profile_sections`. `GithubProvider` is the reference implementation.

Adding a provider = new subclass + one registration entry in `app/providers/__init__.py`. No changes to route handlers, session logic, or `/profile` aggregation.

GitHub uses **PKCE with S256**; `app/core/security.py` generates the code verifier and challenge.

### Token refresh

`TokenRefresher.ensure_fresh()` runs on every authenticated request. It skips tokens with >60s of runway, hard-stops at the 12-hour ceiling, and uses a Redis lock to prevent duplicate refresh attempts under concurrent requests.

### Internal service mock

`InternalServiceClient` (`app/services/internal_service.py`) accepts a custom `httpx` transport. In tests and when `MOCK=true`, `mock_transport_handler` intercepts calls and returns deterministic fixture profiles seeded by `user_id` (seeded RNG — same user always gets same tier/role).

### Logging

`main.py` installs a `_RedactingFilter` on the root logger that strips credential-shaped tokens from all log output before they reach any handler.

## Key technology constraints

- **Python 3.12**: use modern syntax (`X | Y` unions, `type` aliases, `match`).
- **Pydantic v2**: `model_dump()` not `.dict()`, `model_validate()` not `.from_orm()`, validators via `@field_validator`.
- **Async everywhere**: `httpx.AsyncClient` for outbound calls; `redis.asyncio` for Redis. No sync `requests` or sync Redis client.
- **Error hierarchy**: raise `OAuthError`, `ProviderError`, `InternalServiceError`, or `TokenRefreshError` (all in `app/core/exceptions.py`). Exception handlers are registered in `main.py` — don't construct inline HTTP responses.
- **Rate limiting**: `slowapi` `Limiter` (`app/core/rate_limit.py`) is keyed by session cookie, falling back to IP. Storage is wired to Redis in the lifespan.
- **Ruff ignores**: `B008` (FastAPI `Depends()` in defaults) and `UP046` (intentional `Generic[T]` subclassing) are suppressed globally — don't add `# noqa` for these.

## Endpoints

| Method | Path | Rate limit | Description |
|---|---|---|---|
| GET | `/auth/{provider}` | 10/min | Redirect to provider authorization URL |
| GET | `/auth/{provider}/callback` | 20/min | Exchange code, create session, set cookie |
| POST | `/auth/logout` | 30/min | Delete session, clear cookie (token stays alive on provider) |
| DELETE | `/auth/account` | 10/min | Revoke token, delete session, clear cookie |
| GET | `/profile` | 60/min | Return normalized profile (requires session cookie) |
