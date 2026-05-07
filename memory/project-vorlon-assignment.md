---
name: Vorlon Home Assignment
description: Scope, requirements, and constraints for the Vorlon OAuth microservice home assignment driving this repo
type: project
---

Vorlon home assignment: build a microservice that authenticates a user via provider-agnostic OAuth web flow, fetches third-party data (GitHub first), and enriches it with data from a mock internal service. Architecture must support adding providers (Salesforce, Slack, etc.) with minimal changes.

**Why:** This is a take-home for a Vorlon interview; reviewers will judge extensibility, OAuth correctness, security awareness, and code quality. The assignment is expected to take a few hours.

**How to apply:** Treat the GitHub provider as the reference implementation of an abstract OAuth strategy interface — never hardcode GitHub-specific logic into shared paths. Keep the final `/profile` response shape provider-agnostic.

### Endpoints required

- `GET /auth/:provider` — redirect to provider authorization page
- `GET /auth/:provider/callback` — handle code → access token exchange
- `GET /profile` — return aggregated JSON: GitHub repos (name, description, stars) + "Tier" from internal service
- Any additional endpoints needed to support OAuth web flow

### Internal service (mock)

- `GET https://internal-service.local/api/users/:user_id`
- Header: `X-Internal-API-Key: super-secret-key`
- Returns: User ID, Name, License (Pro/Basic), User Role

### GitHub provider data

- Authenticated user's repositories: name, description, stars

### Deliverables

- Minimal UI: trigger GitHub OAuth flow + display unified user/repo data
- README with run instructions
- Attach AI session transcripts (Claude/Cursor) in README
- Be ready to discuss edge cases and security considerations

### Stack (this repo)

- Backend: FastAPI + Pydantic v2 (Python)
- Frontend: Next.js 16 + React 19 + Tailwind v4 + TypeScript
- Language/DB choice is free per the assignment, but stack is already chosen here

### Phased workflow with user

1. Phase 1: Instruction analysis (no code/implementation)
2. Phase 2: Backend implementation planning
3. Phase 3: Frontend implementation planning

**How to apply:** Do not jump phases — wait for explicit user confirmation before moving from analysis → backend plan → frontend plan.
