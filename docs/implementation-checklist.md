# Implementation and verification checklist

Status key: `[x]` implemented and checked, `[~]` implemented but not fully
verified, `[ ]` not implemented, `[!]` blocked by environment or missing input.

## Foundation and architecture

- [x] FastAPI, SQLAlchemy 2, Pydantic 2, PostgreSQL, Alembic, Next.js,
  TypeScript, Tailwind, and a modular API/services/models/schemas structure.
- [x] Architecture decision record, role matrix, lifecycle constraints,
  `COMPANY_CURRENCY` (ISO 4217, default INR), and daily depreciation policy.
- [x] Initial Alembic schema for the application entities; SQLite migration
  upgrade/downgrade/re-upgrade verified.
- [x] Docker Compose definitions, container build files, local startup guide,
  and GitHub Actions CI workflow.

## Security and access

- [x] Argon2 password hashing; short-lived signed access JWTs; opaque refresh
  tokens stored hashed, rotated on use, and revoked as a family on reuse.
- [x] Administrator, Asset Manager, Technician, and Employee/Requester roles
  enforced by backend dependencies and ownership checks.
- [x] Admin user creation/management, protected last active administrator,
  and secure interactive initial-admin CLI.
- [x] CORS allowlist, HttpOnly/SameSite refresh cookie, production secure-cookie
  requirement, sanitized validation responses, and current-user role reload.
- [x] Asset financial details and custodian identity withheld from requester
  summary responses; finance fields protected on report endpoints.
- [~] Threat-focused tests cover roles, auth, refresh replay, validation,
  duplicates, ownership, and workflows. Dedicated automated tests for every
  endpoint/role permutation and browser-level E2E are not yet present.

## Business workflows

- [x] Asset register, categories, locations, bounded pagination/search, and
  duplicate tag/serial protection.
- [x] Allocation, return, transfers, asset retirement, ownership-aware history,
  and QR PNG generation; active assignment constrained in the database.
- [x] Vendors, warranty records, and configurable ISO 4217 company currency.
- [x] Daily straight-line depreciation across actual calendar-life days from
  purchase date (leap years included), capped at residual value, with as-of
  and registry totals.
- [x] Preventive maintenance plans, work requests/orders, assignment, guarded
  status progression, required completion resolution, and history.
- [x] Durable in-app notifications for workflow events and scheduled warranty
  and maintenance reminders; user-scoped read state.
- [x] Transactional audit events and role-protected audit/depreciation/dashboard
  reports.

## Frontend and quality

- [x] Responsive authenticated Next.js screens for dashboard, assets, vendors,
  users, work orders, reports, login, and notification inbox.
- [x] Shared typed API client, bearer token memory, cookie refresh/retry, and
  loading/empty/success/validation/failure feedback.
- [x] Backend: 35 pytest tests passed; Ruff lint/format and Python dependency
  consistency checks passed; migration round-trip passed on SQLite.
- [x] Alembic head migration graph reviewed and PostgreSQL SQL generation
  succeeded offline; no live PostgreSQL migration was run.
- [x] Frontend: ESLint, TypeScript check, 3 Vitest tests, optimized production
  build, and npm audit (0 vulnerabilities) passed.
- [x] GitHub Actions CI defined for backend checks/migrations and frontend
  lint/tests/typecheck/build; workflow has not run on GitHub in this environment.
- [!] PostgreSQL migration execution, locking/concurrency checks, and Compose
  startup/service health could not run: Docker is unavailable and no local
  PostgreSQL listener is available. SQLite is not a substitute for these.
- [~] No browser automation or live frontend-to-PostgreSQL E2E test was run;
  frontend API behavior is covered by unit tests, and backend APIs by SQLite
  integration tests.

## Remaining limits

- Production deployment still requires externally managed TLS, a secret store,
  backups, monitoring, explicit production CORS, and an operational review.
- Email/SMS/push delivery is not configured; notifications are persisted and
  delivered through the in-app inbox.
- The scheduler currently runs a daily reminder scan in one Compose worker;
  high-availability distributed scheduling and retry/dead-letter handling are
  outside this version.
