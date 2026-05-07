# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OAuth flow demo with a **Next.js 16 frontend** and a **FastAPI backend**. The backend has only a `requirements.txt` and virtualenv — no source files exist yet.

## Architecture

```
oauth-flow-demo/
├── frontend/   # Next.js 16.2.5 + React 19 + Tailwind CSS v4, TypeScript
└── backend/    # FastAPI + Pydantic v2 (venv exists, no source files yet)
```

Both Next.js 16 and Tailwind CSS v4 have **breaking changes** from prior versions. Before writing any frontend code, read the relevant docs in `frontend/node_modules/next/dist/docs/` — APIs, conventions, and file structure may differ from training data.

## Commands

### Frontend (run from `frontend/`)

```bash
npm run dev      # start dev server on localhost:3000
npm run build    # production build
npm run lint     # ESLint
```

### Backend (run from `backend/`)

```powershell
.\venv\Scripts\Activate.ps1          # activate virtualenv (PowerShell)
pip install -r requirements.txt      # install deps
uvicorn main:app --reload            # start dev server (once main.py exists)
```

## Key Technology Notes

- **Next.js 16 / React 19**: App Router is the default. Check `node_modules/next/dist/docs/` for current APIs before using Next.js-specific features.
- **Tailwind CSS v4**: Configuration is in `postcss.config.mjs` (not `tailwind.config.js`). The v4 config format differs significantly from v3.
- **Pydantic v2**: Model syntax changed from v1 — use `model_dump()` not `.dict()`, `model_validate()` not `.from_orm()`, etc.
