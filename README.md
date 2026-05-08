# OAuth Flow Demo

A provider-agnostic OAuth microservice that authenticates a user against a third-party identity provider (GitHub, as the reference implementation), enriches the result with data from an internal service, and returns a single normalized profile to the client.

Built as the Vorlon home assignment.

---

## Project Overview

The service brokers the entire OAuth authorization-code flow on the server side. The browser never sees an access token: it holds only an opaque, `HttpOnly` session cookie. The backend exchanges the authorization code, encrypts the resulting tokens at rest in Redis, calls the third-party API on the user's behalf, and aggregates the response with a mock internal service before returning a unified DTO.

The architecture is **provider-agnostic**: GitHub is the first concrete provider, but the OAuth lifecycle (authorize → callback → fetch → refresh → revoke) is defined as an abstract contract. Adding Google, Microsoft, or any OAuth 2.0 + PKCE provider is a matter of writing a new subclass and registering it — no route, session, or aggregation code changes.

The `/profile` endpoint is the single source of truth for the client. It composes:

1. **Provider data** — `GET /user`, `GET /user/repos`, etc. from GitHub.
2. **Internal data** — a mock service returning a deterministic `tier` (Bronze / Silver / Gold) keyed by user id.

The response is shaped by a Pydantic `UnifiedProfile` model so the frontend never deals with provider-specific payloads.

---

## Architecture & Design Patterns

### Strategy Pattern — provider extensibility

`OAuthProvider` (`backend/app/providers/base.py`) is an abstract base class defining the full provider lifecycle:

- `authorization_url(state, code_challenge)`
- `exchange_code(code, code_verifier)`
- `refresh_token(refresh_token)`
- `fetch_user_id(access_token)`
- `revoke_token(access_token)`
- `fetch_profile_sections(access_token)`

`GithubProvider` is the reference concrete strategy. The `app/providers/__init__.py` registry maps a provider slug (`"github"`) to its strategy instance. Route handlers resolve the strategy via dependency injection (`get_provider`) and never branch on provider type. This isolates provider-specific quirks (PKCE handling, scope strings, response shapes) behind the abstract surface.

### Security

| Concern           | Implementation                                                                                                                                                                                              |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Token storage     | Access and refresh tokens are **Fernet-encrypted at rest** in Redis (`app/core/crypto.py`). `TokenCipher` supports key rotation via a fallback list so live sessions survive a key rollover.                |
| Session transport | `HttpOnly`, `SameSite=Lax`, `Secure` in production. The browser holds only an opaque session id.                                                                                                            |
| CSRF              | Per-flow `state` parameter stored in Redis with a short TTL (~5 min) and verified on callback.                                                                                                              |
| OAuth hardening   | **PKCE with S256** code challenge for the GitHub authorization-code flow.                                                                                                                                   |
| Race safety       | Redis writes for state and session records use **Lua scripts** for atomic compare-and-set semantics. A Redis-based lock around token refresh prevents duplicate refresh attempts under concurrent requests. |
| Refresh ceiling   | A 12-hour hard ceiling is enforced — past that, the session is treated as expired regardless of refresh-token state.                                                                                        |
| Rate limiting     | `slowapi` limiter wired into auth and profile routes.                                                                                                                                                       |
| Secrets           | All secrets are loaded via Pydantic `SecretStr` from `.env` (gitignored); none are logged.                                                                                                                  |

### Session management

Redis is the session store. Three record types live under typed keys:

- `state:{id}` — short-TTL CSRF state and PKCE verifier.
- `session:{id}` — encrypted tokens, provider id, sliding-expiry TTL.
- `profile:{user_id}` — cached normalized profile.

The session store layer (`app/services/session_store.py`) is the only module that talks to Redis directly; everything else goes through it.

---

## Tech Stack

| Layer         | Technology                                                     |
| ------------- | -------------------------------------------------------------- |
| Frontend      | React 19, Vite 8, JSX                                          |
| Backend       | Python 3.11+, FastAPI, Pydantic v2, `httpx` (async), `slowapi` |
| Session store | Redis 7                                                        |
| Crypto        | `cryptography` (Fernet / AES-128-CBC + HMAC-SHA256)            |
| Tests         | `pytest`, `pytest-asyncio`, `respx`                            |
| Container     | Docker / Docker Compose (Redis)                                |

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for Redis) — or a local Redis 7 install
- A GitHub OAuth App (Settings → Developer settings → OAuth Apps)
  - **Authorization callback URL**: `http://localhost:8000/auth/github/callback`

### 1. Start Redis

```bash
docker compose up -d redis
```

Or, equivalently:

```bash
docker run -d --name oauth-redis -p 6379:6379 redis:7-alpine
```

### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then fill in the values below
uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

### Environment variables (`backend/.env`)

| Variable                | Description                                                                                                                                        |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GITHUB_CLIENT_ID`      | OAuth App client id                                                                                                                                |
| `GITHUB_CLIENT_SECRET`  | OAuth App client secret                                                                                                                            |
| `GITHUB_REDIRECT_URI`   | `http://localhost:8000/auth/github/callback`                                                                                                       |
| `INTERNAL_SERVICE_URL`  | Base URL of the (mock) internal service                                                                                                            |
| `INTERNAL_API_KEY`      | API key for the internal service                                                                                                                   |
| `INTERNAL_SERVICE_MOCK` | `true` to use the in-process mock transport                                                                                                        |
| `REDIS_URL`             | `redis://localhost:6379/0`                                                                                                                         |
| `SESSION_SECRET`        | 32-byte url-safe base64 key for Fernet (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `FRONTEND_ORIGIN`       | `http://localhost:5173` (CORS allowlist)                                                                                                           |
| `POST_LOGIN_REDIRECT`   | URL to redirect to after successful callback                                                                                                       |
| `ENV`                   | `dev` or `prod`                                                                                                                                    |
| `SESSION_TTL_SECONDS`   | Session sliding expiry (default `3600`)                                                                                                            |
| `STATE_TTL_SECONDS`     | OAuth state TTL (default `300`)                                                                                                                    |

---

## API Documentation

All endpoints are mounted at the backend root (`http://localhost:8000`).

### `GET /auth/{provider}`

Initiates the OAuth flow. Generates `state` + PKCE `code_verifier`, stores them in Redis, and **302-redirects** the browser to the provider's authorization URL.

- Path params: `provider` — currently `github`.
- Response: `302 Found` with `Location: <provider authorization url>`.

### `GET /auth/{provider}/callback`

The provider redirects here with `?code=…&state=…`. The backend:

1. Validates `state` against the Redis record.
2. Exchanges the code for tokens (with PKCE verifier).
3. Encrypts the tokens and writes a session record.
4. Sets the session cookie (`HttpOnly`, `SameSite=Lax`).
5. **302-redirects** to `POST_LOGIN_REDIRECT`.

Errors return a structured JSON body via the `OAuthError` / `ProviderError` handlers.

### `GET /profile`

Returns the unified profile for the current session. Requires the session cookie.

- Auth: session cookie.
- Response: `200 OK` with a `UnifiedProfile` JSON body — user summary, repos (from GitHub), and `tier` (from the internal service).
- Errors: `401` if the cookie is missing or the session has expired past the refresh ceiling.

A token refresh — if needed — happens transparently inside this handler; the client does not see it.

---

## Claude Code Sessions (public)

Public Claude Code session links recorded during the build:

- `https://claude.ai/code/session_019DhvbjSBnmh1aVzXKS7xhA`
- _TBD — paste session URL here_
- _TBD — paste session URL here_

These cover the analysis, backend planning, and implementation phases.

---

## What I Would Add With More Time

- **Second provider implementation** (Google or Microsoft) to exercise the strategy abstraction beyond a single concrete case and surface any leaky assumptions in the base class.
- **Real internal service** instead of the in-process mock transport, plus a small contract test suite so the aggregation layer is verified against an actual HTTP boundary.
- **End-to-end tests with Playwright** driving the full redirect chain in a headless browser, including the negative paths (state mismatch, expired refresh token, revoked grant).
- **Observability**: structured JSON logging, OpenTelemetry traces across the OAuth flow, and per-provider metrics (token-refresh success rate, callback latency, 4xx/5xx rates).
- **Production session store hardening**: Redis ACLs, TLS, and a dedicated logical DB; secrets sourced from a secret manager (AWS Secrets Manager / Vault) instead of `.env`.
- **CI pipeline** (GitHub Actions) running lint, type-check (`mypy --strict`), unit tests, and a docker-compose-based integration test job.
- **Frontend polish**: a real design system (shadcn/ui or Radix), proper loading/error states, and a TypeScript migration so the `UnifiedProfile` shape is shared end-to-end.
- **Token revocation on logout** wired through to the provider, not just session deletion.
- **Audit log** of auth events (login, refresh, revoke, failure) written to a separate append-only stream.
