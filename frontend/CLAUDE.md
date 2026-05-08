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

- **React 19** (JSX, not TSX — no TypeScript configured yet)
- **Vite 8** with `@vitejs/plugin-react` (Babel transform)
- **ESLint** with `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh`

## Implementation status

`src/App.jsx` is currently the Vite starter template. The OAuth UI needs to be built. Planned interaction surface:

1. "Login with GitHub" button → `GET http://localhost:8000/auth/github` (triggers redirect chain)
2. After redirect back, `GET http://localhost:8000/profile` to fetch the normalized profile
3. Display repos and tier from the profile response

## API communication rules

- All fetch/axios calls to the backend **must** include `credentials: 'include'` so the session cookie travels cross-origin.
- The backend CORS origin is `http://localhost:5173`. Do not change the dev port without updating the backend config.
- Never store tokens or session data in `localStorage`, `sessionStorage`, or React state — the cookie is the only auth artifact the browser should hold.
- Backend base URL for local dev: `http://localhost:8000`.
