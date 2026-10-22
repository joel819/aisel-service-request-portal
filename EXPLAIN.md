# EXPLAIN.md (for Joel, not the graders)

## What every file does

### Root
- `.env.example` - template listing every environment variable with safe placeholder values.
- `.gitignore` - keeps `.env`, virtualenvs, `node_modules` and build output out of git.
- `.github/workflows/ci.yml` - GitHub Actions job that builds the stack and runs `pytest` in the api container.
- `docker-compose.yml` - defines the `db`, `api` and `web` services, the database healthcheck and the `pgdata` volume.
- `README.md` - setup, architecture, API table, limitations and assumptions for the graders.
- `EXPLAIN.md` - this file.

### backend/
- `Dockerfile` - builds the Python 3.12 image, installs pinned requirements and copies the app.
- `.dockerignore` - keeps caches and virtualenvs out of the image.
- `requirements.txt` - pinned Python dependencies.
- `pytest.ini` - tells pytest to look in `tests/`.
- `alembic.ini` - Alembic configuration (script location and logging).
- `alembic/env.py` - tells Alembic which metadata and database URL to use; a URL set on the config (as the tests do) wins over the app setting.
- `alembic/script.py.mako` - template Alembic uses when generating new migrations.
- `alembic/versions/0001_initial.py` - creates the three enum types, `users`, `service_requests`, the indexes and CHECK constraints.
- `alembic/versions/0002_audit_and_roles.py` - adds `users.role` and the `audit_logs` table.
- `app/__init__.py`, `app/routers/__init__.py`, `app/services/__init__.py`, `scripts/__init__.py`, `tests/__init__.py` - empty package markers.
- `app/main.py` - builds the FastAPI app: CORS, routers, `/api/health` and the catch-all 500 handler returning `{"detail": ...}`.
- `app/config.py` - `Settings` loaded from environment variables via pydantic-settings, cached by `get_settings()`.
- `app/database.py` - SQLAlchemy engine, `SessionLocal`, declarative `Base` and the `get_db` dependency.
- `app/models.py` - `User`, `ServiceRequest` and `AuditLog` ORM models plus the `ServiceType`, `Priority`, `Status`, `Role` and `AuditAction` enums.
- `app/schemas.py` - Pydantic models for login, user output and service request create/update/output/page.
- `app/llm.py` - talks to the language model: an OpenAI-compatible HTTP client with streaming, retries and timeouts, plus an offline `MockLLM` used by tests, evals and the demo.
- `app/guardrails.py` - code-level protections for the assistant: tool allow-list and call cap, untrusted-data wrapping, and the link/image filter (also usable on streamed text).
- `app/security.py` - bcrypt hash/verify and JWT create/decode.
- `app/deps.py` - `get_current_user` (Bearer token to `User`, else 401) and `require_admin` (403 for non-admins).
- `app/routers/auth.py` - `POST /api/auth/login` and `GET /api/auth/me`.
- `app/routers/assistant.py` - `POST /api/assistant/ask`: auth, rate limit, then streams the assistant's events as Server-Sent Events.
- `app/routers/requests.py` - the five `/api/requests` endpoints; only HTTP concerns.
- `app/services/auth.py` - `authenticate()`: look up the user and check the password.
- `app/services/requests.py` - list/filter/paginate, get, create, update and delete queries; writes audit rows.
- `app/services/assistant.py` - the assistant loop: asks the model, runs the tools it requests, feeds results back, streams the filtered answer, and logs tokens and cost.
- `app/services/assistant_tools.py` - the three read-only tools (`search_requests`, `get_request`, `count_requests`), their validated arguments, and `run_tool`, which never raises.
- `app/services/audit.py` - `record()` stages an audit-log row in the caller's transaction.
- `app/services/rate_limit.py` - in-memory sliding-window limiter used by login.
- `scripts/seed_user.py` - creates the first user (as admin) from `SEED_USER_EMAIL`/`SEED_USER_PASSWORD`, or promotes it if it exists without the role.
- `tests/conftest.py` - creates the test database, runs migrations, and provides `db`, `user`, `client` and `auth_headers` fixtures.
- `tests/test_auth.py` - login, 401, token and rate-limit tests.
- `tests/test_requests.py` - CRUD workflow, validation, 404, delete, filter and admin-only-delete tests.
- `tests/test_assistant.py` - the assistant through the HTTP API: answers with tools, permission checks, prompt injection, step cap, timeouts, rate limit, logging.
- `tests/test_assistant_tools.py`, `tests/test_guardrails.py`, `tests/test_llm.py` - the tools, the output filter, and the provider client (mocked HTTP, no network).
- `tests/assistant_helpers.py` - small helpers and a scripted fake model for those tests.
- `tests/test_evals.py` - runs the evals in CI and proves the gate fails when it should.
- `evals/testset.jsonl`, `evals/run_evals.py` - 10 graded questions with expected request ids, and the runner that builds a throwaway database, runs them and exits 1 on regressions.
- `ruff.toml` - lint rules.
- `tests/test_audit.py` - checks create, update and delete each write an audit row with the user.

### frontend/
- `Dockerfile` - builds the Next.js app with `NEXT_PUBLIC_API_URL` baked in and starts it.
- `.dockerignore`, `.gitignore` - exclude `node_modules` and build output.
- `package.json`, `package-lock.json` - pinned frontend dependencies and scripts.
- `tsconfig.json` - strict TypeScript configuration.
- `next.config.mjs` - Next.js config (defaults).
- `postcss.config.mjs`, `tailwind.config.ts` - Tailwind setup.
- `app/globals.css` - Tailwind layers plus shared `.input` and `.btn*` classes.
- `app/layout.tsx` - root HTML shell and page title.
- `app/page.tsx` - redirects `/` to `/requests`.
- `app/login/page.tsx` - login form; stores the token and redirects on success.
- `app/requests/layout.tsx` - wraps the request pages with the header.
- `app/requests/page.tsx` - list with search, filters, pagination, table (desktop) and cards (phone).
- `app/requests/new/page.tsx` - create page using `RequestForm`.
- `app/requests/[id]/edit/page.tsx` - loads one request, quick status/priority, edit form and confirm-before-delete.
- `components/Badge.tsx` - colour-coded priority and status badges.
- `components/Header.tsx` - top bar with log out.
- `components/RequestForm.tsx` - shared create/edit form with client-side validation matching the backend.
- `components/States.tsx` - loading, error and empty-state components.
- `app/assistant/page.tsx`, `app/assistant/layout.tsx` - the "Ask the assistant" page that shows the answer as it streams.
- `lib/api.ts` - the single fetch wrapper: adds the token, maps errors, clears the token and redirects on 401.
- `lib/types.ts` - TypeScript types, enum value lists and the `label()` helper.

## How a request flows

### Login
1. `app/login/page.tsx` `handleSubmit` calls `api("/api/auth/login", {method: "POST", ...})` from `lib/api.ts` (with `redirectOn401: false` so a bad password shows an error instead of redirecting).
2. FastAPI routes it to `login()` in `routers/auth.py`, and Pydantic validates the body as `LoginRequest`.
3. `login()` calls `services/auth.py::authenticate`, which loads the user by lower-cased email (`select(User).where(...)`) and runs `security.verify_password` (bcrypt). Unknown email and wrong password both return `None`.
4. On `None` the router raises `HTTPException(401, "Invalid credentials")`. Otherwise `security.create_access_token` signs `{sub, exp}` with `JWT_SECRET` (HS256).
5. The response is `{access_token, token_type, expires_in}`. The page calls `setToken()` (localStorage) and `router.replace("/requests")`.

### Creating a request
1. `app/requests/new/page.tsx` renders `RequestForm`; on submit `validate()` in `components/RequestForm.tsx` checks lengths client-side.
2. `create()` calls `api("/api/requests", {method: "POST", body})`; `lib/api.ts` adds `Authorization: Bearer <token>`.
3. FastAPI runs the router-level dependency `deps.get_current_user`: it reads the Bearer header, `security.decode_access_token` verifies signature and expiry, then `db.get(User, id)`. Any failure is a 401.
4. Pydantic validates the body as `ServiceRequestCreate` (422 if invalid).
5. `routers/requests.py::create_request` calls `services/requests.py::create_request`, which builds a `ServiceRequest` with `created_by_id`, adds it, commits and refreshes.
6. Postgres fills `id`, the generated `reference`, `created_at` and `updated_at`; the router returns `ServiceRequestOut` with status 201.
7. The page navigates to `/requests`, where `load()` fetches the list again.

### Asking the assistant
1. `app/assistant/page.tsx` `ask()` calls `askAssistant()` in `lib/api.ts`, which POSTs the question with the Bearer token and reads the response body as a stream.
2. `deps.get_current_user` checks the token (401 if bad), then `routers/assistant.py::ask` checks the per-user rate limit (429) and builds the model client with `llm.get_llm` (503 if not configured).
3. `services/assistant.py::ask` sends the stable system prompt plus today's date and your question to the model through `llm.stream_chat`, passing the three tool definitions.
4. If the model asks for a tool, `_run_call` first checks `ToolPolicy` (allow-list, 5-call cap), then `assistant_tools.run_tool` validates the arguments and calls `services/requests.py` **with the signed-in user**. `_visible_to` there is what limits non-admins to their own requests. The result goes back to the model wrapped by `wrap_untrusted`.
5. Text from the model passes through `SafeTextStream` (links and images removed) and is sent as `token` events. When the loop ends, one log line records the tokens, cost and time, and a `done` event is sent.

## Likely interview questions

1. **Why JWT?** The API is stateless and consumed by a separate SPA, so a signed token avoids a session store. The cost is that tokens cannot be revoked before expiry; mine expire after 60 minutes and there is no refresh flow.
2. **Why bcrypt?** It is deliberately slow and salts each hash, so leaked hashes are expensive to crack. I call `bcrypt` directly (`security.py`) with its default cost factor. Argon2 would also be a fine choice.
3. **Why Alembic?** Schema changes are versioned and repeatable, so a fresh clone and production end up with the same schema. The tests also run the migrations, so a broken migration fails the suite.
4. **Why a services layer?** Routers only translate HTTP to function calls. The query and update logic lives in `services/`, which has no FastAPI imports, so it is easy to read, test and reuse.
5. **How is SQL injection prevented?** All access goes through SQLAlchemy expressions, which send values as bound parameters. The search term is also escaped for `LIKE` wildcards (`_escape_like`), and there are no raw SQL strings in the app.
6. **What happens with an expired token?** `jwt.decode` raises `ExpiredSignatureError`, `decode_access_token` returns `None`, `get_current_user` raises 401, and `lib/api.ts` clears localStorage and redirects to `/login`.
7. **Why PATCH, not PUT?** The UI changes single fields (quick status/priority), so a partial update fits. `ServiceRequestUpdate` uses `exclude_unset` so only sent fields change, and explicit nulls are rejected.
8. **Why are tokens in localStorage?** It is simple and works across the separate frontend and API origins. The trade-off is XSS exposure; httpOnly cookies would be stronger but need CSRF protection. It is noted in the README.
9. **Why enums and CHECK constraints in the database as well as Pydantic?** Pydantic protects the API, but the database is the last line of defence against bad data from scripts, migrations or future code paths.
10. **What would you improve next?** Refresh tokens or cookie auth, soft delete, a read endpoint and field-level detail for the audit log, role management, and a shared (Redis) rate limiter. The current limiter is in memory per process, which is listed under known limitations.
11. **How does the rate limit and RBAC work?** `services/rate_limit.py` keeps recent attempt times per client IP and the login router returns 429 after 10 in a minute. `deps.require_admin` checks `user.role` and the delete route depends on it, so non-admins get 403; the frontend also hides the delete button, but the API is what enforces it.
12. **How do you stop the assistant seeing other users' data?** In code, not in the prompt. The user comes from the JWT, never from the model. Every tool calls the same service functions as the REST API, and `_visible_to` in `services/requests.py` limits non-admins to rows they created. Tool arguments forbid extra fields, so a made-up `user_id` is rejected. A test uses a model that does whatever injected text says and shows it still cannot read another user's request.
13. **What is prompt injection, and what happens if a description contains it?** A request description is text written by users, and the model reads it as part of a tool result, so it could contain instructions. Wrapping it as untrusted data and telling the model to ignore it helps a little, but the real protection is limits: read-only tools, an allow-list, a 5-call cap, per-user data scoping, and an output filter that removes links and images so nothing can be leaked through a URL. `test_prompt_injection_in_a_description_does_not_change_behaviour` and evals q09 and q10 cover it.
14. **Why a mock model, and how do you know the evals mean something?** The mock makes tests and the demo free and deterministic, and it exercises the real tools, database and guardrails. It does not measure language quality, so with a real model you would run the same evals and adjust. I checked the evals can fail by removing the permission rule: five cases failed, three of them critical, and the exit code was 1.
15. **Why SSE instead of WebSockets, and why not `EventSource`?** The answer only flows one way, server to browser, and SSE is plain HTTP. `EventSource` cannot send a POST body or an Authorization header, so the frontend reads the stream with `fetch` instead. If the model is down before any output, the API returns a real 502 or 504, because the first event is checked before the stream starts.
16. **What would you add next for the assistant?** Conversation memory with consent and limits, a daily spend cap per user using the logged token costs, a shared (Redis) rate limiter, a judge-based eval for answer quality, and a team or assignee model so "my requests" can mean more than "ones I created".
