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

The AI assistant sits on the same layers (details in [AI assistant](#ai-assistant)):

```
Browser "Ask the assistant" box
  |  POST /api/assistant/ask  {"question": "..."}  + Bearer JWT      <- streamed back as SSE
FastAPI router (auth, rate limit, input limits)
  |
services/assistant.py   the loop: model -> tool calls -> results -> model -> answer
  |        |                         |
  |        |  tools (read-only,      |  guardrails.py: tool allow-list, 5-step cap,
  |        |  run as the user)       |  untrusted-data wrapping, link/image filter
  |        v
  |   services/requests.py  <-- the SAME visibility rule as the normal API
  |        |                    (admin: all requests, everyone else: only their own)
  |        v
  |   PostgreSQL
  v
app/llm.py   OpenAI-compatible HTTP client (any provider)  or  the offline mock
```

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
| httpx + OpenAI-compatible API | The assistant talks to any provider that speaks `/chat/completions` (OpenAI, DeepSeek, Groq, Ollama...), configured by env vars. No SDK is needed and no provider is hard-coded. |

## Setup

Requires Docker with the Compose plugin.

```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD, JWT_SECRET (openssl rand -hex 32) and SEED_USER_PASSWORD
docker compose up -d --build
```

Then open <http://localhost:3000> and sign in with `SEED_USER_EMAIL` / `SEED_USER_PASSWORD` from your
`.env`. Swagger docs are at <http://localhost:8000/docs>.

The app refuses to start while `JWT_SECRET` or `SEED_USER_PASSWORD` still hold the `change-me...`
placeholders from `.env.example`.

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
| `LLM_PROVIDER` | `mock` (default: offline, no key, deterministic) or `openai` (any OpenAI-compatible API). |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Required when `LLM_PROVIDER=openai`. Get current model names from your provider's docs; none is hard-coded. The key stays on the server and is never sent to the browser or logged. |
| `LLM_PRICE_IN`, `LLM_PRICE_CACHED`, `LLM_PRICE_OUT` | Optional. USD per 1M tokens from your provider's pricing page, used only to log the cost of each question. |
| `LLM_TIMEOUT_S` | Time budget for one assistant question, default 30. |

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

Lint (ruff, configured in `backend/ruff.toml`) and the assistant evals:

```bash
docker compose run --rm --no-deps api sh -c "pip install -q --user ruff==0.17.1 && ~/.local/bin/ruff check ."
docker compose run --rm api python -m evals.run_evals
(cd frontend && npm install && npm run lint)
```

## API overview

| Method | Path | Auth | Description | Success |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | no | Liveness check | 200 |
| POST | `/api/auth/login` | no | Exchange email and password for a JWT (10 attempts per minute per IP, then 429) | 200 / 401 / 429 |
| GET | `/api/auth/me` | yes | Current user | 200 |
| GET | `/api/requests` | yes | List with `q`, `status`, `priority`, `service_type`, `page`, `page_size` (max 100). Admins see all requests, other users only their own | 200 |
| POST | `/api/requests` | yes | Create a request | 201 |
| GET | `/api/requests/{id}` | yes | Get one request | 200 / 404 |
| PATCH | `/api/requests/{id}` | yes | Partial update | 200 / 404 / 422 |
| DELETE | `/api/requests/{id}` | admin | Hard delete | 204 / 403 / 404 |
| POST | `/api/assistant/ask` | yes | Ask the AI assistant a question; the answer streams back as Server-Sent Events (20 questions per minute per user) | 200 / 401 / 422 / 429 / 502 / 503 / 504 |

Requests belonging to someone else return 404 (not 403) for non-admins, so their ids cannot be probed.

Extras: every create, update and delete writes a row to `audit_logs` (action, request id and
reference, user, timestamp) in the same transaction as the change. The table is not exposed through
the API; query it in the database. Users have a role (`admin` or `user`); only admins can delete. The
seed user is an admin. A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the test suite.

Errors use `{"detail": "..."}`; validation errors keep FastAPI's 422 format. Missing, invalid or
expired tokens return 401.

**Delete is a hard delete.** The brief asked for a delete and a soft delete would add a column and
extra filtering everywhere; the row is removed permanently. An audit trail or soft delete would be the
next step if recoverability matters.

## AI assistant

Staff can ask in plain English, for example "show urgent requests from this week", "summarise request
#42" or "how many requests are still open for client Acme?". The answer streams into the **Assistant**
page (`/assistant`) as it is written.

**How it works.** The model never writes SQL. It is given three read-only tools and can only fill in
their arguments:

| Tool | Arguments | Used for |
| --- | --- | --- |
| `search_requests` | filters (text, client, statuses, priorities, service type, dates), `limit` (max 20) | listing and finding requests |
| `get_request` | `request_id` | summarising one request |
| `count_requests` | the same filters | "how many" questions |

Each tool calls the same service functions as the normal API, as the signed-in user. A question may use
at most 5 tool calls and 30 seconds. Every question logs one line with the tool names, prompt, cached and
completion tokens, cost (if prices are configured), latency and prompt version, never the question text.

**Setup.**

1. Nothing to do for a demo: `LLM_PROVIDER=mock` is the default. The mock reads the question, calls the
   real tools against the real database and writes the answer from the results, so you can try the whole
   flow without a key. It is deterministic, which is why the tests and evals use it.
2. For a real model, set `LLM_PROVIDER=openai`, `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in `.env`
   (any OpenAI-compatible provider; check its docs for current model names), then
   `docker compose up -d --build`. If they are missing the endpoint returns 503 instead of failing later.
3. Log in, open **Assistant**, ask. Try it from the command line:

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"<SEED_USER_EMAIL>","password":"<SEED_USER_PASSWORD>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -N localhost:8000/api/assistant/ask -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"question":"show urgent requests from this week"}'
```

The stream has four event types: `tool` (a tool is running), `token` (a piece of the answer), `error`
and `done`. If the model is unreachable before any output, the API returns 502 (504 on timeout) instead
of a stream.

**Evals.** `backend/evals/testset.jsonl` holds 10 questions, each with the request ids the answer must
contain, run as one of three fake users (an admin and two normal users) against a fixed fake dataset in a
throwaway `<database>_eval` database. `python -m evals.run_evals` grades each answer with rules (ids and
counts), safety checks (other users' data and injected links must never appear) and trajectory checks
(expected tools called, forbidden tools never). It exits 1 below a 90% pass rate or if any critical case
fails, and `pytest` runs it in CI. With the mock it checks the plumbing; run it with a real model to also
measure answer quality (wording differs, so expect to adjust cases). Removing the permission rule makes it
fail, which was checked while building it.

## Security

Who can see what is decided in code, not in the prompt.

- **One access rule for everything.** `services/requests.py` applies the rule "admins see every request,
  everyone else only their own" to listing, reading, counting, updating and deleting. The REST API, the
  UI and the assistant tools all use these functions, so the assistant can never see more than the user
  can through the normal API. Other people's requests return "not found", the same as a missing id.
- **The model cannot choose the user.** The user comes from the verified JWT. Tool arguments are validated
  Pydantic models that forbid extra fields, so a `user_id` argument is rejected rather than ignored.
- **Read-only, allow-listed tools.** Only the three tools above exist. Any other name (for example a
  `delete_request` the model invents) is refused in code, and at most 5 tool calls run per question.
- **Request text is untrusted.** Descriptions and client names are written by users and could contain
  prompt injection. Tool results are wrapped and labelled as data, and the system prompt says never to
  follow them. That is only a soft defence: the guarantees above hold even when the model is fooled, which
  the tests prove with a model that obeys the injected text.
- **No links or images in answers.** Every answer is filtered as it streams: markdown links keep their
  text, markdown images, raw URLs and risky HTML tags are removed, so injected text cannot exfiltrate
  data through an image URL or a link. The frontend renders answers as plain text.
- **Limits and secrets.** Questions are limited to 1000 characters, 20 per minute per user, 5 tool calls and
  30 seconds. The provider key is only read from the environment on the server, is wrapped in `SecretStr`
  and is not logged. Provider errors are logged but never shown to the client.
- **Same JWT as the rest of the API.** Missing or invalid tokens get 401 before any model call is made.

OWASP Top 10 for LLM applications (2025 list):

| Risk | Handled by |
| --- | --- |
| LLM01 Prompt injection | Scoped read-only tools, allow-list, step cap, untrusted wrapping, output filter, injection tests and evals |
| LLM02 Sensitive information disclosure | The shared access rule, no `created_by` in tool results, nothing sensitive in the prompt, question text never logged |
| LLM05 Improper output handling | Link, image and HTML filter; plain-text rendering |
| LLM06 Excessive agency | Three read-only tools, no write tools at all |
| LLM07 System prompt leakage | The prompt holds no secrets or access rules |
| LLM10 Unbounded consumption | Rate limit, input length, 5 tool calls, 30 seconds, `max_tokens` on every call |
| LLM03, LLM04, LLM08, LLM09 | Not applicable here (no model training, no vector store); answers come from tool results only |

## Known limitations

- The frontend uses Next.js 14.2.35, which `npm audit` flags; the only fix is a major upgrade to
  Next 16, which I did not attempt. Build-time tooling (Tailwind/PostCSS) also has advisories but
  does not run in production. Backend dependencies were audited with `pip-audit` and are clean.
- The containers run as non-root users, but `/docs` (Swagger) is open and the database uses a
  single superuser account; both would need tightening in production.
- The JWT is stored in `localStorage`, so any XSS bug on the page could read it. httpOnly, SameSite
  cookies would be stronger (at the cost of CSRF handling and a same-site API setup).
- No refresh tokens: the user is sent back to login when the token expires.
- The login rate limit is in memory and per API process (keyed by client IP, which is the proxy's IP
  behind a reverse proxy); a shared store such as Redis would be needed with several workers.
- Only two roles; there is no endpoint to change a user's role, and the audit log has no read endpoint.
- The assistant rate limit, like the login one, is in memory and per process.
- The assistant has no conversation memory: every question is answered on its own.
- The assistant sends request text (client names, descriptions) to whichever LLM provider you configure.
  Use only providers you are allowed to share this data with, or the mock, and never real customer data in
  a demo.
- Prompt-injection defences reduce risk but cannot remove it. The hard limits are the permission rule, the
  read-only tools and the output filter.
- Non-admin users now only see their own requests in the UI and the API; before the assistant was added,
  every user saw every request.
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
- The assistant treats "urgent" as priority high or critical and "open" as new, in review or in progress.
- Dates in assistant questions are UTC calendar days, and weeks start on Monday.
- Request ownership means the user who created it (`created_by_id`); there is no assignee or team model.
- Only the Compose workflow is documented; running the API or frontend outside Docker is not covered.

## Time spent

Approximate time spent: 12 hours. The core brief took roughly the 6-hour budget; the rest went into extras (audit log, roles, rate limiting, CI, container hardening) and into learning parts of the stack I hadn't used together before.
