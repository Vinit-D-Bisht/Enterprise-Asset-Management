# Enterprise Asset & Maintenance Management System (EAMMS)

EAMMS is a modular asset register and maintenance application built as a
student-level, production-style project. PostgreSQL is the system of record;
the API enforces permissions and business invariants for every workflow.

## Stack and structure

- **API:** FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL, Alembic, Argon2,
  short-lived JWT access tokens, rotating opaque refresh cookies.
- **Web:** Next.js App Router, TypeScript, Tailwind CSS, responsive UI.
- **Services:** PostgreSQL 16 and a separate daily notification scheduler via
  Docker Compose.
- `backend/app/api/v1`: HTTP routes; `schemas`: request/response validation;
  `services`: transactional domain operations; `models`: persistence.
- `backend/alembic`: versioned database migrations; `backend/tests`: API and
  business lifecycle tests.
- `frontend/app/(protected)`: authenticated operational pages; `lib/api.ts`:
  shared API and session refresh client.
- `docs/architecture.md`: role matrix and domain invariants;
  `docs/implementation-checklist.md`: implemented and verified scope.

## Features

- Four backend-enforced roles: Administrator, Asset Manager, Technician, and
  Employee/Requester, including record ownership checks.
- Admin user management and initial admin creation CLI; Argon2 password
  hashing; access token in memory; HttpOnly, SameSite refresh cookie with
  hashed, rotating refresh tokens and token-family reuse revocation.
- Asset, category, and location registers with search/pagination; allocation,
  return, transfer, retirement, assignment history, and QR code generation.
- Vendor and warranty management; configurable ISO 4217 company currency.
- Daily straight-line depreciation prorated over the actual calendar-day life
  from purchase date (including leap days), capped at residual value, with
  as-of reporting.
- Maintenance plans, work requests/orders, technician assignment, status and
  resolution tracking, notifications, audit history, dashboard and reports.
- Database constraints and row locks protect key lifecycle operations and
  prevent multiple active assignments to one asset.

## Local startup (PowerShell)

Prerequisites: Docker Desktop with Compose, Python 3.12+, Node.js 20.19+, and
npm. From the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` and set `JWT_SECRET_KEY` to a unique random value of at least 32
characters. Set `COMPANY_CURRENCY` to the organization's ISO 4217 alpha-3 code.
For a deployment, set `CORS_ORIGINS` to the browser origin(s) and
`NEXT_PUBLIC_API_BASE_URL` to the public API URL before building the web image.
The frontend formats money using the API's `company_currency` response field,
which comes from `COMPANY_CURRENCY`.
Do not commit `.env`. Then launch the integrated stack:

```powershell
docker compose up --build -d
```

Compose starts PostgreSQL, applies Alembic migrations before the API becomes
healthy, then starts the web app and daily notification scheduler. Create the first
administrator (the command prompts securely for a password):

```powershell
docker compose exec api python -m app.cli create-admin --email admin@example.com --name "System Administrator"
```

Open `http://localhost:3000`; API docs are at `http://localhost:8000/docs`,
with liveness and database readiness at `/health` and `/health/ready`.

For API-only development, start PostgreSQL with `docker compose up -d db`,
then from `backend` create/activate a virtual environment, run
`python -m pip install -r requirements.txt`, and start
`alembic upgrade head` followed by `uvicorn app.main:app --reload`.
For frontend-only development, from `frontend` run `npm ci` and `npm run dev`.

## Checks

Backend, from `backend`:

```powershell
python -m pytest -q -p no:cacheprovider
python -m ruff check app tests alembic
alembic upgrade head
```

Frontend, from `frontend`:

```powershell
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

## Security and deployment notes

The supplied `.env.example` credentials are for local development only. In a
deployment use a managed secret store, TLS, `APP_ENV=production`,
`COOKIE_SECURE=true`, explicit production CORS origins, database backups, and
reviewed database access controls. Compose binds ports to loopback by default;
publish the web app and API only through a TLS reverse proxy, and keep the
database private. Do not expose the development API docs publicly without an
access policy. The readiness endpoint checks database connectivity; liveness
does not.

See the implementation checklist for checks that need a local PostgreSQL and
Docker environment and for current testing limits.
