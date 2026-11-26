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
  secure interactive initial-admin CLI, and one-time transactional first-run
  setup with optional sample data.
- [x] Department CRUD with administrator-only backend authorization, unique
  normalized names, user assignments, and reference-aware delete conflicts.
- [x] Persistent Light, Dark, and System theme preferences across app routes.
- [x] CORS allowlist, HttpOnly/SameSite refresh cookie, production secure-cookie
  requirement, sanitized validation responses, and current-user role reload.
- [x] Persistent database-backed login throttling: five failed attempts per
  email/IP pair and 30 per IP in a 15-minute window; identifiers are HMACed.
- [x] JWT dependency audit: replaced python-jose/ecdsa with explicit HS256-only
  PyJWT; requirements audit reports no known vulnerabilities.
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
- [x] Protected depreciation and audit CSV exports; spreadsheet formula cells
  are neutralized and audit exports omit event detail payloads.

## Frontend and quality

- [x] Responsive authenticated Next.js screens for dashboard, assets, vendors,
  users, departments, catalogs, work orders, reports, login/setup, and
  notification inbox.
- [x] Shared typed API client, bearer token memory, cookie refresh/retry, and
  loading/empty/success/validation/failure feedback.
- [x] Backend: 64 pytest tests passed; Ruff lint/format, pip check, and pip-audit
  passed. Migration chain was tested from a fresh PostgreSQL database and the
  new throttle migration was applied additively to the existing PostgreSQL DB.
- [x] Live PostgreSQL Department schema matches migration definitions,
  including `ix_users_department_id`, the department FK, and normalized unique
  index. Existing row counts and the named PostgreSQL data volume were preserved.
- [x] Frontend: ESLint, TypeScript check, 16 Vitest tests, optimized production
  build, and npm audit (0 vulnerabilities) passed.
- [x] Playwright browser suite: first-run setup with sample data, all four role
  logins/menus, asset allocation/return/transfer, work orders/preventive plans,
  reports and protected CSV downloads, role restrictions, three themes,
  preference persistence, and a 390px responsive overflow check passed against
  disposable PostgreSQL.
- [x] PostgreSQL concurrency test submitted eight parallel invalid login
  attempts; four returned 401 and subsequent attempts were throttled with 429.
- [x] CI workflow includes a browser E2E job on an isolated Compose stack; it
  has not run on GitHub from this environment.

## Remaining limits

- Production deployment still requires externally managed TLS, a secret store,
  backups, monitoring, explicit production CORS, and an operational review.
- Browser tests cover the initial setup with sample data; empty setup is covered
  by backend tests, but has not been separately exercised in Playwright.
- Email/SMS/push delivery is not configured; notifications are persisted and
  delivered through the in-app inbox.
- The scheduler currently runs a daily reminder scan in one Compose worker;
  high-availability distributed scheduling and retry/dead-letter handling are
  outside this version.
