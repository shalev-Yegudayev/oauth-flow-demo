# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role

Thin React client. Its only job is to initiate the OAuth flow (redirect to backend) and display the normalized profile returned by `GET /profile`. It holds **no auth state** — all OAuth credentials and session data live in the backend. The session is maintained via an `HttpOnly` cookie set by the backend.

## Commands

```bash
npm install
npm run dev      # Vite dev server on http://localhost:5173
npm run build    # production build → dist/
npm run preview  # serve the production build locally
npm run lint     # ESLint
```

## Stack

- **React 19** with **TypeScript** (`.tsx`)
- **Vite** with `@vitejs/plugin-react`
- **TanStack Query** for server state, **Zod** for response validation, **Tailwind** for styling
- **ESLint** with `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh`

## Implementation status

The OAuth UI is in place: `LoginPage` triggers the backend redirect chain, `ProfilePage` (guarded by `AuthGuard`) renders the unified profile from `GET /profile`, and provider-specific sections render through a discriminated `provider` field. Logout and account-deletion buttons live on the profile header.

## API communication rules

- All fetch/axios calls to the backend **must** include `credentials: 'include'` so the session cookie travels cross-origin.
- The backend CORS origin is `http://localhost:5173`. Do not change the dev port without updating the backend config.
- Never store tokens or session data in `localStorage`, `sessionStorage`, or React state — the cookie is the only auth artifact the browser should hold.
- Backend base URL for local dev: `http://localhost:8000`.
