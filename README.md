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
| Container     | Docker / Docker Compose (full stack)                           |

---

## Setup & Installation

### Prerequisites

- A GitHub OAuth App (Settings → Developer settings → OAuth Apps)
  - **Authorization callback URL**: `http://localhost:8000/auth/github/callback`
- Docker (required for both options below)
- Python 3.11+ and Node.js 20+ (Option B only)

---

### Option A — Full stack via Docker Compose (recommended)

```powershell
# 1. Copy and fill in secrets
copy backend\.env.example backend\.env   # fill in the values listed below

# 2. Build images and start all three services
docker compose up --build
```

| Service  | URL                      |
| -------- | ------------------------ |
| Frontend | http://localhost:5174    |
| Backend  | http://localhost:8000    |
| Redis    | localhost:6379 (internal)|

To stop: `docker compose down` (add `-v` to also wipe the Redis volume).

---

### Option B — Local development

#### 1. Start Redis

```bash
docker compose up -d redis
```

#### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then fill in the values below
uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`.

#### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

> **Note:** when running locally, `FRONTEND_ORIGIN` and `POST_LOGIN_REDIRECT` in `backend/.env` must point to `http://localhost:5173`, not `5174`.

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

- Overall setup and backend design — _(paste session URL)_
- Backend Implementation — `https://claude.ai/code/session_019DhvbjSBnmh1aVzXKS7xhA`
- Frontend Implementation — `https://claude.ai/code/session_019wymAUK6rh2yk5gFmHqLDf`

These cover the analysis, backend planning, and implementation phases.

---

## What I Would Add With More Time

### Features

- **Second provider implementation** (Google or Microsoft) to exercise the strategy abstraction beyond a single concrete case and surface any leaky assumptions in the base class.
- **Real internal service** instead of the in-process mock transport, plus a small contract test suite so the aggregation layer is verified against an actual HTTP boundary.
- **Token revocation on logout** wired through to the provider, not just local session deletion.
- **Active session management UI** — let users see all live sessions (device, IP, last-used timestamp) and revoke individual ones, backed by a `sessions:{user_id}` index in Redis.
- **Multi-provider concurrent sessions** — allow a user to link GitHub, Google, and Microsoft accounts under a single identity, with a merge/conflict resolution strategy for duplicate emails.
- **Provider-side revocation webhooks** — GitHub (and Google) can push a notification when a token is revoked externally; the backend should listen and immediately invalidate the corresponding session.

### Security

- **Refresh token rotation** — issue a new refresh token on every use and invalidate the previous one. A replayed old refresh token signals a possible token theft and should trigger session teardown.
- **HTTPS / TLS in production** — TLS termination at the load balancer or reverse proxy, `Secure` cookie flag enforced by `ENV=prod`, and HSTS headers (`Strict-Transport-Security`).
- **mTLS or signed JWTs for the internal service** — replace the plain `INTERNAL_API_KEY` header with mutual TLS or short-lived JWTs so the internal service can verify the caller's identity, not just a static secret.
- **Suspicious-session detection** — flag (and optionally invalidate) sessions where the IP or user-agent changes mid-session, or where a token refresh is attempted from an unexpected geo-region.
- **Secrets rotation pipeline** — automate `SESSION_SECRET` rotation end-to-end: provision a new key, add it to the Fernet fallback list, re-encrypt live sessions in a background job, then retire the old key. Currently this is documented but not automated.

### Observability & Operations

- **Structured JSON logging** with a correlation id per request, and redacted sensitive fields.
- **OpenTelemetry traces** across the full OAuth flow (authorize → callback → profile fetch → internal service call).
- **Per-provider metrics**: token-refresh success rate, callback latency p95, 4xx/5xx rates — exported to Prometheus / Grafana.
- **Audit log** of all auth events (login, refresh, revoke, failure) written to a separate append-only stream (Redis Streams or a dedicated table).
- **Production session store hardening**: Redis ACLs, TLS, a dedicated logical DB, and secrets sourced from a secret manager (AWS Secrets Manager / Vault) rather than `.env`.

### Developer Experience

- **CI pipeline** (GitHub Actions) running lint, type-check (`mypy --strict`), unit tests, and a docker-compose-based integration test job on every PR.
- **End-to-end tests with Playwright** driving the full redirect chain in a headless browser, including negative paths (state mismatch, expired refresh token, revoked grant).
- **Frontend polish**: TypeScript migration so the `UnifiedProfile` shape is shared end-to-end, a real design system (shadcn/ui or Radix), and proper loading / error states.
