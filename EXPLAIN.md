# EXPLAIN.md (for Joel, not the graders)

## What every file does

### Root
- `.env.example` - template listing every environment variable with safe placeholder values.
- `.gitignore` - keeps `.env`, virtualenvs, `node_modules` and build output out of git.
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
- `app/__init__.py`, `app/routers/__init__.py`, `app/services/__init__.py`, `scripts/__init__.py`, `tests/__init__.py` - empty package markers.
- `app/main.py` - builds the FastAPI app: CORS, routers, `/api/health` and the catch-all 500 handler returning `{"detail": ...}`.
- `app/config.py` - `Settings` loaded from environment variables via pydantic-settings, cached by `get_settings()`.
- `app/database.py` - SQLAlchemy engine, `SessionLocal`, declarative `Base` and the `get_db` dependency.
- `app/models.py` - `User` and `ServiceRequest` ORM models plus the `ServiceType`, `Priority` and `Status` enums.
- `app/schemas.py` - Pydantic models for login, user output and service request create/update/output/page.
- `app/security.py` - bcrypt hash/verify and JWT create/decode.
- `app/deps.py` - `get_current_user`, which turns a Bearer token into a `User` or raises 401.
- `app/routers/auth.py` - `POST /api/auth/login` and `GET /api/auth/me`.
- `app/routers/requests.py` - the five `/api/requests` endpoints; only HTTP concerns.
- `app/services/auth.py` - `authenticate()`: look up the user and check the password.
- `app/services/requests.py` - list/filter/paginate, get, create, update and delete queries.
- `scripts/seed_user.py` - creates the first user from `SEED_USER_EMAIL`/`SEED_USER_PASSWORD` if absent.
- `tests/conftest.py` - creates the test database, runs migrations, and provides `db`, `user`, `client` and `auth_headers` fixtures.
- `tests/test_auth.py` - login, 401 and token tests.
- `tests/test_requests.py` - CRUD workflow, validation, 404, delete and filter tests.

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
10. **What would you improve next?** Roles so only admins can delete, an audit log for changes, rate limiting on login, refresh tokens or cookie auth, and soft delete. None are implemented, which is why they are listed under known limitations.
