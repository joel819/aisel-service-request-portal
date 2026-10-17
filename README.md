# Service Request & Project Intake Portal

## Overview

A small web app for authenticated team members to record and manage client service requests:
create, search and filter, change status and priority, edit, and delete. It consists of a FastAPI
backend, a PostgreSQL database and a Next.js frontend, all started with one `docker compose` command.

## Architecture

```
Browser
  |
Next.js (App Router, TypeScript, Tailwind)      :3000
  |  fetch + Bearer JWT (lib/api.ts)
FastAPI (routers -> services)                   :8000
  |  SQLAlchemy 2.0 ORM
PostgreSQL 16 (enum types, CHECK constraints)   internal to compose network
```

Backend layering: `routers/` handle HTTP only (status codes, auth dependency, 404s);
`services/` hold the business logic and all queries; `models.py` defines the tables;
`schemas.py` defines request/response validation.

## Technology choices and why

| Choice | Why |
| --- | --- |
| FastAPI + Pydantic v2 | Typed request validation, correct 422 responses and Swagger docs at `/docs` for free. |
| SQLAlchemy 2.0 (typed) + Alembic | ORM queries are parameterised (no string SQL); migrations make the schema reproducible. |
| PostgreSQL 16 | Native enum types and CHECK constraints reject invalid values at the database level. |
| bcrypt (direct) | Slow, salted password hashing; used directly rather than through passlib to avoid its maintenance and compatibility issues. |
| PyJWT (HS256) | Stateless tokens; the API needs no session store. |
| Next.js + TypeScript + Tailwind | Simple routed pages with typed API calls and no UI kit. |
| Docker Compose | One command for db, api and web, with a health-checked database. |

## Setup

Requires Docker with the Compose plugin.

```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD, JWT_SECRET (openssl rand -hex 32) and SEED_USER_PASSWORD
docker compose up -d --build
```

Then open <http://localhost:3000> and sign in with `SEED_USER_EMAIL` / `SEED_USER_PASSWORD` from your
`.env`. Swagger docs are at <http://localhost:8000/docs>.

On start the `api` container waits for the database to be healthy, runs `alembic upgrade head`,
runs `scripts/seed_user.py` (does nothing if the user already exists) and starts uvicorn.

## Environment variables

All configuration comes from `.env` (read by Docker Compose). `.env` is git-ignored; `.env.example`
lists every variable with placeholder values.

| Variable | Purpose |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Database credentials and name used by the `db` service. Use URL-safe characters in the password. |
| `DATABASE_URL` | SQLAlchemy URL used by the API (`postgresql+psycopg://...@db:5432/...`). |
| `TEST_DATABASE_URL` | Separate database used by pytest; created automatically if missing. |
| `JWT_SECRET` | HS256 signing key (at least 16 characters; use a long random value). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime, default 60. |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. |
| `SEED_USER_EMAIL`, `SEED_USER_PASSWORD` | Credentials of the first user created by the seed script. |
| `NEXT_PUBLIC_API_URL` | API base URL used by the browser. Baked in at frontend build time. |

## Database setup and migrations

Migrations live in `backend/alembic/versions/` and run automatically on API start. To run them manually:

```bash
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic current
```

To create a new migration after changing `models.py`:

```bash
docker compose run --rm api alembic revision --autogenerate -m "describe change"
```

The database is only reachable inside the Compose network (its port is not published, to avoid
clashing with a Postgres already running on the host). The named volume `pgdata` keeps data between
restarts; `docker compose down -v` deletes it.

## Run commands

```bash
docker compose up -d --build      # start db, api, web
docker compose logs -f api        # follow API logs
docker compose down               # stop (keeps data)
docker compose down -v            # stop and delete the database volume
```

## Test commands

```bash
docker compose run --rm api pytest -q
```

Tests run against a separate database (`TEST_DATABASE_URL`). The suite recreates the schema by running
the Alembic migrations once per session, seeds a test user per test and clears all tables after each
test, so tests do not depend on each other.

## API overview

| Method | Path | Auth | Description | Success |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | no | Liveness check | 200 |
| POST | `/api/auth/login` | no | Exchange email and password for a JWT (10 attempts per minute per IP, then 429) | 200 / 401 / 429 |
| GET | `/api/auth/me` | yes | Current user | 200 |
| GET | `/api/requests` | yes | List with `q`, `status`, `priority`, `service_type`, `page`, `page_size` (max 100) | 200 |
| POST | `/api/requests` | yes | Create a request | 201 |
| GET | `/api/requests/{id}` | yes | Get one request | 200 / 404 |
| PATCH | `/api/requests/{id}` | yes | Partial update | 200 / 404 / 422 |
| DELETE | `/api/requests/{id}` | admin | Hard delete | 204 / 403 / 404 |

Extras: every create, update and delete writes a row to `audit_logs` (action, request id and
reference, user, timestamp) in the same transaction as the change. The table is not exposed through
the API; query it in the database. Users have a role (`admin` or `user`); only admins can delete. The
seed user is an admin. A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the test suite.

Errors use `{"detail": "..."}`; validation errors keep FastAPI's 422 format. Missing, invalid or
expired tokens return 401.

**Delete is a hard delete.** The brief asked for a delete and a soft delete would add a column and
extra filtering everywhere; the row is removed permanently. An audit trail or soft delete would be the
next step if recoverability matters.

## Known limitations

- The JWT is stored in `localStorage`, so any XSS bug on the page could read it. httpOnly, SameSite
  cookies would be stronger (at the cost of CSRF handling and a same-site API setup).
- No refresh tokens: the user is sent back to login when the token expires.
- The login rate limit is in memory and per API process (keyed by client IP, which is the proxy's IP
  behind a reverse proxy); a shared store such as Redis would be needed with several workers.
- Only two roles; there is no endpoint to change a user's role, and the audit log has no read endpoint.
- No user management UI; additional users need the seed script or direct database access.
- Hard delete only; the audit log keeps who deleted what, but the data itself is gone.
- `NEXT_PUBLIC_API_URL` is fixed at frontend build time, so changing it needs a rebuild.
- Search uses `ILIKE` with a leading wildcard, which is fine at this scale but will not use an index.

## Assumptions and trade-offs

- `reference` is a Postgres generated column (`'SR-' || lpad(id, 5, '0')`), so it is always consistent
  with the id and needs no second write.
- Page size on the list screen is 10; the API default is 20 as specified.
- Status can be set when creating through the API (default `new`); the create form only exposes priority.
- Emails are matched case-insensitively (stored lower-cased); login treats email as a plain string so a
  malformed address gets the same 401 as a wrong one.
- PATCH rejects explicit `null` for any field because every field is required in the database.
- Names and descriptions are trimmed before the length rules are applied.
- Ordering of the list is newest first (`created_at`, then `id`).
- Passwords are hashed with bcrypt's default cost; a dummy hash is checked for unknown emails so both
  failures take similar time.
- The audit log records the action, not the changed field values.
- Only the Compose workflow is documented; running the API or frontend outside Docker is not covered.

## Time spent

Approximate time spent: 12 hours
