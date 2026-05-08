# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OAuth flow demo (Vorlon home assignment) — a provider-agnostic OAuth microservice that authenticates a user, fetches third-party data (GitHub first), enriches it with a mock internal service, and returns a normalized profile.

| Layer | Stack | Dev URL |
|---|---|---|
| Frontend | React 19 + Vite 8 (JSX) | `http://localhost:5173` |
| Backend | Python + FastAPI + Pydantic v2 | `http://localhost:8000` |
| Session store | Redis 7 | `localhost:6379` |

Each sub-project has its own `CLAUDE.md` with full detail:
- [backend/CLAUDE.md](backend/CLAUDE.md)
- [frontend/CLAUDE.md](frontend/CLAUDE.md)

## Starting the full stack

```powershell
# 1. Redis
docker run -d --name oauth-redis -p 6379:6379 redis:7-alpine

# 2. Backend (from backend/)
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload

# 3. Frontend (from frontend/)
npm run dev
```

## Key cross-cutting constraints

- The browser never receives an access token — the backend holds all OAuth credentials in Redis, encrypted.
- Frontend API calls must include `credentials: 'include'` so the session cookie is sent cross-origin.
- CORS is configured on the backend for `http://localhost:5173` with `allow_credentials=True`.
- All secrets live in `backend/.env` (gitignored). See `backend/.env.example` for the full list.
