# OAuth Flow Demo

Provider-agnostic OAuth microservice (Vorlon home assignment). Authenticates a user against a third-party provider (GitHub), enriches the result with a mock internal service, and returns a single normalized profile.

---

## Project Overview

- The backend brokers the full authorization-code flow; the browser only ever holds an opaque `HttpOnly` session cookie.
- Tokens are encrypted at rest in Redis. The backend calls the provider API on the user's behalf.
- `/profile` returns a unified DTO composed of **provider data** (GitHub `/user`, `/user/repos`) and **internal data** (mock service returning a deterministic `license` of `Pro` or `Basic`, plus a `role`).
- Provider-agnostic by design: adding Google/Microsoft = new subclass + one registry entry. No route or session changes.

---

## Architecture & Design Patterns

**Strategy pattern.** `OAuthProvider` (`backend/app/providers/base.py`) defines the lifecycle (`authorization_url`, `exchange_code`, `refresh_token`, `fetch_user_id`, `revoke_token`, `fetch_profile_sections`). `GithubProvider` is the reference implementation; routes resolve it via DI and never branch on provider type.

**Security.**

| Concern         | Implementation                                                                  |
| --------------- | ------------------------------------------------------------------------------- |
| Token storage   | Fernet-encrypted at rest with key-rotation fallback list (`app/core/crypto.py`) |
| Session cookie  | `HttpOnly`, `SameSite=Lax`, `Secure` in production — opaque session id only     |
| CSRF            | Per-flow `state` in Redis with short TTL, verified on callback                  |
| OAuth hardening | PKCE S256 on the authorization-code flow                                        |
| Race safety     | Lua scripts for atomic state/session writes; Redis lock around token refresh    |
| Refresh ceiling | 12-hour hard cap regardless of refresh-token state                              |
| Rate limiting   | `slowapi` on auth and profile routes                                            |
| Secrets         | Pydantic `SecretStr` from `.env`; never logged                                  |

**Session store.** Redis holds three typed records: `oauth:state:{id}` (CSRF + PKCE verifier, short TTL), `oauth:session:{id}` (encrypted tokens, sliding TTL), `oauth:user:{provider}:{user_id}` (cached internal profile, namespaced per provider). `app/services/session_store.py` is the only module that talks to Redis.

**Security headers.** A small middleware (`main.py`) attaches `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, and (in production) HSTS to every response.

**Open-redirect guard.** `POST_LOGIN_REDIRECT` is validated at startup: it must be on the configured `FRONTEND_ORIGIN`, otherwise the app refuses to boot.

---

## Tech Stack

| Layer         | Technology                                             |
| ------------- | ------------------------------------------------------ |
| Frontend      | React 19, Vite, TypeScript, Tailwind, TanStack Query   |
| Backend       | Python 3.11+, FastAPI, Pydantic v2, `httpx`, `slowapi` |
| Session store | Redis 7                                                |
| Crypto        | `cryptography` (Fernet)                                |
| Tests         | `pytest`, `pytest-asyncio`, `respx`                    |
| Container     | Docker / Docker Compose                                |

---

## Setup & Installation

Two ways to run the project — choose the one that fits your goal.

---

### Option 1 — Docker Compose (recommended for local evaluation)

Runs the full stack (frontend, backend, Redis) in isolated containers with a single command.

**Prerequisites:** Docker

```powershell
# 1. Copy the environment template and fill in your secrets
copy backend\.env.example backend\.env

# 2. Build images and start all services
docker compose up --build
```

| Service  | URL                       |
| -------- | ------------------------- |
| Frontend | http://localhost:5174     |
| Backend  | http://localhost:8000     |
| Redis    | localhost:6379 (internal) |

To stop: `docker compose down` (add `-v` to also remove the Redis volume).

---

### Option 2 — Local development

Runs each service on the host for the fastest iteration cycle. Requires a Redis container for the session store.

**Prerequisites:** Docker, Python 3.11+, Node.js 20+

#### 1. Redis

```bash
docker run -d --name oauth-redis -p 6379:6379 redis:7-alpine
```

#### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # fill in the values listed below
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

> **Note:** when using Option 2, ensure `FRONTEND_ORIGIN` and `POST_LOGIN_REDIRECT` in `backend/.env` are set to `http://localhost:5173` (not `5174`).

### Environment variables (`backend/.env`)

| Variable                   | Description                                                                                                                                        |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GITHUB_CLIENT_ID`         | OAuth App client id                                                                                                                                |
| `GITHUB_CLIENT_SECRET`     | OAuth App client secret                                                                                                                            |
| `GITHUB_REDIRECT_URI`      | `http://localhost:8000/auth/github/callback`                                                                                                       |
| `INTERNAL_SERVICE_URL`     | Base URL of the (mock) internal service                                                                                                            |
| `INTERNAL_API_KEY`         | API key for the internal service                                                                                                                   |
| `INTERNAL_SERVICE_MOCK`    | `true` to use the in-process mock transport                                                                                                        |
| `REDIS_URL`                | `redis://localhost:6379/0`                                                                                                                         |
| `SESSION_SECRET`           | 32-byte url-safe base64 key for Fernet (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `FRONTEND_ORIGIN`          | `http://localhost:5173` (CORS allowlist)                                                                                                           |
| `POST_LOGIN_REDIRECT`      | URL to redirect to after successful callback                                                                                                       |
| `ENV`                      | `dev` or `production`                                                                                                                              |
| `SESSION_TTL_SECONDS`      | Session sliding expiry (default `3600`)                                                                                                            |
| `STATE_TTL_SECONDS`        | OAuth state TTL (default `300`)                                                                                                                    |
| `USER_PROFILE_TTL_SECONDS` | Internal-service profile cache TTL (default `3600`)                                                                                                |

### Environment variables (`frontend/.env`)

Vite inlines `VITE_*` variables into the bundle at build time, so they must be set before `npm run build` (or `docker compose build`), not at container start.

| Variable                    | Description                                                                                                            |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `VITE_BACKEND_API_BASE_URL` | Backend origin the SPA calls (e.g. `http://localhost:8000`). Must match the host the browser can reach the backend on. |

---

## API Documentation

All endpoints live under `http://localhost:8000`.

| Method   | Path                        | Auth           | Description                                                                                                                                |
| -------- | --------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET`    | `/auth/{provider}`          | —              | Generates `state` + PKCE verifier, 302 to provider authorization URL.                                                                      |
| `GET`    | `/auth/{provider}/callback` | —              | Validates `state`, exchanges code, encrypts tokens, sets session cookie, 302 to `POST_LOGIN_REDIRECT`.                                     |
| `POST`   | `/auth/logout`              | session cookie | Deletes the local session and clears the cookie. The provider-side token is left alive (use `DELETE /auth/account` to revoke it). `204`.   |
| `DELETE` | `/auth/account`             | session cookie | Revokes the access token at the provider, deletes the session, clears the cookie. Revocation failures are logged but do not block. `204`.  |
| `GET`    | `/profile`                  | session cookie | Returns `UnifiedProfile` (user, repos, `license`). Refreshes the token transparently if needed. `401` if expired past the refresh ceiling. |

Errors are returned as structured JSON via the `OAuthError` / `ProviderError` handlers.

---

## Claude Code Sessions (public)

Public session artifacts recorded during the build, in chronological order:

| #   | Phase                          | Link                                                                                                             |
| --- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| 1   | Setup & backend design         | [docs/Vorlon home assignment phase one - setup.md](docs/Vorlon%20home%20assignment%20phase%20one%20-%20setup.md) |
| 2   | Backend implementation         | https://claude.ai/code/session_019DhvbjSBnmh1aVzXKS7xhA                                                          |
| 3   | Frontend implementation        | https://claude.ai/code/session_019wymAUK6rh2yk5gFmHqLDf                                                          |
| 4   | Backend CR & security analysis | https://claude.ai/code/session_01BRnpXzz4Pu4BeLRGnUwNZy                                                          |

Together these cover the analysis, planning, implementation, and review phases.

---

## What I Would Add With More Time

**Features**

- Second provider (Google/Microsoft) to exercise the strategy abstraction
- Real internal service with contract tests
- Multi-provider account linking

**Security**

- Explicit redirect URI validation — store the provider's expected `redirect_uri` in the state record; validate on callback that the incoming parameter matches, preventing accidental misconfiguration
- Refresh-token rotation with replay detection
- mTLS or signed JWTs for the internal service (instead of a static API key)
- Suspicious-session detection (IP/UA/geo changes)
- Automated `SESSION_SECRET` rotation pipeline

**Observability**

- Structured JSON logs with per-request correlation IDs
- OpenTelemetry traces across the full flow
- Per-provider Prometheus metrics (refresh success, callback p95, error rates)
- Append-only audit log
- Hardened prod Redis (ACLs, TLS, secret manager)

**Developer Experience**

- GitHub Actions CI (lint, `mypy --strict`, tests, compose-based integration job)
- Playwright E2E covering negative paths
- Real design system (shadcn/Radix) and frontend test coverage (Vitest + RTL)
