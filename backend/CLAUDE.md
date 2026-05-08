# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role

FastAPI backend: OAuth broker, session manager, and profile aggregator. The frontend never sees an access token — this service is the only party that holds OAuth credentials, speaks to GitHub, and calls the internal mock service.

## Commands

```powershell
.\venv\Scripts\Activate.ps1          # activate virtualenv
pip install -r requirements.txt      # install deps
uvicorn main:app --reload            # dev server on http://localhost:8000
```

### Tests

```powershell
pytest                               # run all tests
pytest tests/test_auth.py -k "login" # run single test by name
pytest -x                            # stop on first failure
```

Test stack: `pytest-asyncio` for async test functions, `respx` for mocking `httpx` calls.

### Redis (required)

```bash
docker run -d --name oauth-redis -p 6379:6379 redis:7-alpine
```

## Module map

```
backend/
├── main.py        # FastAPI app factory, lifespan (Redis + httpx), CORS, slowapi  [NOT YET CREATED]
├── deps.py        # DI providers: get_redis, get_http_client, get_session_store,
│                  #               get_provider, get_authenticated_session         [NOT YET CREATED]
├── config.py      # Pydantic Settings — all secrets/TTLs loaded from .env
└── app/
    ├── core/      # exceptions.py, crypto.py, security.py, rate_limit.py
    ├── models/    # session.py (StateRecord, SessionRecord, UserProfileRecord)
    │              # profile.py (UnifiedProfile, UserSummary DTOs)
    ├── providers/ # base.py (OAuthProvider ABC), github.py, __init__.py (registry)
    ├── services/  # session_store.py, internal_service.py, token_refresher.py
    └── routes/    # auth.py, profile.py  [NOT YET CREATED]
```

**Implementation status**: `app/core/`, `app/models/`, `app/providers/`, `app/services/` are complete. `main.py`, `deps.py`, `app/routes/`, and `tests/` still need to be created. The full plan lives in `memory/BACKEND_IMPLEMENTATION_PLAN.md`.

## Architecture

### Session & token security

- Session cookie: `HttpOnly`, `SameSite=Lax` (survives the OAuth redirect chain), `Secure` in production. The browser holds only an opaque session ID.
- Access tokens are Fernet-encrypted (`app/core/crypto.py`, AES-128-CBC). `TokenCipher` supports key rotation — retired keys stay in a fallback list so live sessions survive a key rollover.
- Redis state records use a short TTL (~5 min) for CSRF protection; session records use a longer TTL with sliding expiry.
- `session_store.py` uses Lua scripts for atomic Redis operations to prevent race conditions on concurrent requests.

### Provider abstraction

`OAuthProvider` (abstract, `app/providers/base.py`) defines the lifecycle: `authorization_url`, `exchange_code`, `refresh_token`, `fetch_user_id`, `revoke_token`, `fetch_profile_sections`. `GithubProvider` is the reference implementation.

Adding a provider requires only a new subclass and a registration entry in `app/providers/__init__.py` — no changes to route handlers, session logic, or the `/profile` aggregation layer.

GitHub uses **PKCE with S256**; `app/core/security.py` generates the code verifier and challenge.

### Token refresh

`app/services/token_refresher.py` refreshes on first read after expiry. A Redis-based lock prevents duplicate refresh attempts under concurrent requests. There is a **12-hour hard ceiling** — no refresh is attempted past that point regardless of token state.

### Internal service mock

`app/services/internal_service.py` uses a custom HTTPX transport that returns deterministic fixture data seeded by `user_id` (no real network call). The mock returns a `tier` field (Bronze / Silver / Gold) consumed by `/profile`.

## Key technology constraints

- **Pydantic v2**: `model_dump()` not `.dict()`, `model_validate()` not `.from_orm()`, validators via `@field_validator`.
- **Async everywhere**: `httpx.AsyncClient` for outbound calls; `redis.asyncio` for Redis. No sync `requests` or sync Redis client — both must compose with FastAPI's event loop.
- **Error hierarchy**: raise `OAuthError`, `ProviderError`, `InternalServiceError`, or `TokenRefreshError` (all in `app/core/exceptions.py`). Exception handlers are registered there — don't construct inline HTTP responses.
- **Rate limiting**: `slowapi` `Limiter` lives in `app/core/rate_limit.py` and must be wired into the FastAPI app in `main.py`.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/auth/{provider}` | Redirect to provider authorization URL |
| GET | `/auth/{provider}/callback` | Exchange code, create session, set cookie |
| GET | `/profile` | Return normalized profile (requires session cookie) |
