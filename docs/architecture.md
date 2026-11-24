# EAMMS architecture

## System boundaries

- **Frontend:** Next.js App Router, TypeScript, and Tailwind CSS. It renders
  workflows and calls the backend API. Access tokens remain in application
  memory; refresh tokens are HttpOnly cookies.
- **Backend:** FastAPI exposes versioned REST endpoints. Pydantic validates
  inputs and outputs. Routers perform request/response work; services enforce
  business rules and own transactions; SQLAlchemy models persistence.
- **Database:** PostgreSQL is the production database. Alembic owns schema
  changes. SQLite is used only for fast isolated tests.
- **Infrastructure:** Docker Compose runs PostgreSQL locally. Secrets and
  deployment values are supplied through environment variables.

## Backend modules

`api/v1` contains routers for authentication, users, assets, vendors, and
maintenance. `services` contains authorization-aware business operations,
audit recording, notifications, and depreciation calculation. `models` defines
relational entities and database constraints. `schemas` defines API contracts.
`core` contains configuration, password/token handling, and access policies.

The dependency direction is API -> services -> models/database. Services do
not import FastAPI request objects. Database sessions are request-scoped, and
each state-changing service commits its business changes and audit event in one
transaction.

## Identity and authorization

The four roles are Administrator, Asset Manager, Technician, and
Employee/Requester. Authorization is enforced in backend dependencies and
service-level ownership checks:

| Capability | Administrator | Asset Manager | Technician | Employee/Requester |
| --- | --- | --- | --- | --- |
| Manage users and roles | Yes | No | No | No |
| Manage assets, locations, vendors, warranties | Yes | Yes | No | No |
| Allocate, return, and transfer assets | Yes | Yes | No | No |
| Read asset register | Yes | Yes | Yes | Yes |
| Create maintenance plans and assign work | Yes | Yes | No | No |
| Update assigned work orders | Yes | Yes | Yes, assigned only | No |
| Request maintenance | Yes | Yes | Yes | Yes |
| View reports and audit history | Yes | Yes, reports only | No | No |

Passwords use Argon2. Login issues short-lived signed access JWTs and an opaque
rotating refresh token. Only a hash of each refresh token is persisted. Refresh
tokens are HttpOnly, SameSite cookies; logout revokes the current token. User
role and active status are loaded from the database for each authenticated API
request so role changes and account deactivation take effect immediately.
Initial administrator creation is an explicit CLI operation, never an open
public signup endpoint.

## Core data and invariants

- Users have normalized unique email addresses and one of the four roles.
- Assets have unique asset tags and optional unique serial numbers, category,
  location, vendor, purchase data, and residual value/useful life.
- Only one active assignment may exist per asset. A partial unique database
  index enforces this; allocation and return lock the asset row in PostgreSQL.
- Allocation, return, and transfer records are historical and are not deleted.
- Transfers record source and destination and update the asset location in the
  same transaction.
- Warranties and maintenance plans retain their source records. Work orders
  record requester, assignee, status, due date, and completion.
- Every important state change writes an audit record in the same transaction.
- Notifications are durable user-scoped records created with their triggering
  operation.
- Straight-line depreciation is daily prorated over the actual calendar-day
  useful-life interval from purchase date, including leap days, capped at the
  depreciable basis (cost minus residual value), and never reduces book value
  below residual value. The report accepts an explicit as-of date.
  Financial amounts use one configurable ISO 4217 `COMPANY_CURRENCY` (default
  `INR`), returned to the frontend as `company_currency`.

## API and frontend integration

All business routes live under `/api/v1`. Responses use explicit Pydantic
schemas; errors use HTTP status codes and a stable `detail` shape. Lists use
bounded page/page-size parameters. The frontend uses one typed API client,
handles 401 by attempting refresh once, and displays loading, empty, success,
validation, and failure states. UI visibility is convenience only; the backend
remains authoritative for every permission check.

## Verification strategy

- Unit tests cover password/token helpers, authorization, and depreciation.
- API/integration tests use an isolated database to cover auth, validation,
  role denials, duplicates, lifecycle operations, and audit/notification writes.
- Alembic is tested from an empty database where a database service is
  available. SQLite integration tests provide local coverage but do not replace
  PostgreSQL concurrency and migration verification.
- Frontend checks include typecheck, lint, production build, and component/API
  behavior tests where tooling is available.
- CI runs Python and frontend checks. Docker Compose health is verified when
  Docker is available.
