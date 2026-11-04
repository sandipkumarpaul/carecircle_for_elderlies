# CareCircle for Elderlies

A web application for coordinating medication adherence and family caregiving.

**BRAC University · CSE470 · Fall 2026 · Group 7 · Section 10**

## Current implementation

Sandip's Sprint 1 delivers **CC-01: Care circle and consent access**, with supporting authentication and database infrastructure. Authentication is not counted as an assessed feature.

| Area | Implemented behavior |
|---|---|
| Accounts | Registration, login/logout, Argon2 password hashing, normalized unique email |
| Sessions | Eight-hour JWT sessions in HttpOnly cookies, database revocation, CSRF/origin checks, authentication rate limits |
| Patients | Personal and dependent profiles with explicit consent/authority records |
| Care circles | Expiring single-use invitations, matching-account acceptance, primary/secondary roles, selected permissions, access changes and revocation |
| Shared infrastructure | Patient-scoped permission service, audit records, deduplicated internal alerts and recipient/delivery records |
| Persistence | MySQL models and initial Alembic migration `0001_sandip` |
| Interface | Responsive account, patient-profile and caregiver-access screens |

Invitations use a private link copied and shared manually. SMTP delivery, email verification/password recovery, clinical workflows CC-02–CC-20, scheduling, OCR and risk prediction are **not implemented**. Internal alert persistence is not a completed alert-center feature. See [implementation status](docs/status.md) and [validation evidence](VALIDATION.md).

## Start here after cloning

1. Follow the setup below and run the existing application before changing it.
2. Read [Sandip's implementation and handoff](docs/sandip-sprint-1.md) for request flows, limits and the demonstration procedure.
3. Find your ownership and next tasks in [team responsibilities](docs/team.md) and [sprint plan](docs/sprints.md).
4. Read [architecture](docs/architecture.md), [database design](docs/data-model.md) and [shared contracts](docs/contracts.md).
5. Follow [CONTRIBUTING.md](CONTRIBUTING.md), including migration coordination and required checks.

Reuse the implemented accounts, patients, sessions and permission service. Extend the migration chain from `0001_sandip`; do not create another initial schema. The full-project database document includes planned tables, so check the current models/migrations before assuming a feature exists.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite 7, MUI 7 |
| Backend | FastAPI, Pydantic, synchronous SQLAlchemy 2, PyMySQL |
| Database / migrations | MySQL 8.4, Alembic |
| Authentication | PyJWT, Argon2, HttpOnly cookies, server-side session records |
| Development runtimes | Python 3.12, Node.js 24 |
| Tests | pytest, real MySQL integration tests, Playwright |

Exact package versions are recorded in `backend/requirements.lock.txt` and `frontend/package-lock.json`. Future OCR and risk modules will remain inside the FastAPI backend. See the [dependency inventory](docs/dependencies.md). The team reports faculty approval for FastAPI as the full backend; retain the exception evidence in the course submission records.

## Repository structure

```text
backend/
  app/controllers/     HTTP requests, authentication dependencies and transaction boundaries
  app/core/            Configuration, database connection and security primitives
  app/models/          SQLAlchemy persistence models
  app/schemas/         Validated input types and shared contracts
  app/services/        Access rules, consent/invitation workflows and alert persistence
  migrations/          Versioned database schema changes
  tests/               Contract, HTTP, MySQL and browser-server support tests
frontend/
  src/views/           Account and care-circle screens
  src/components/      Shared UI components
  src/lib/             API client and frontend types
  tests/               Browser workflow tests
docs/                  Architecture, contracts, ownership, scope and handoff
scripts/               Local startup/shutdown and documentation checks
.github/               CI workflow and pull-request template
```

## Local setup

Install Python 3.12, Node.js 24 and MySQL 8.4. Using your database administrator account, create a `carecircle` database with `utf8mb4` and a dedicated application account with privileges only on that database. The application must not connect as root. Database binaries and user data are not bundled with this repository.

From the repository root in PowerShell:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
Copy-Item backend/.env.example backend/.env
```

Edit `backend/.env`: set `DATABASE_URL` with your account/password/host/port, keep `APP_ORIGIN=http://localhost:5173`, and replace `JWT_SECRET` with a random value of at least 32 characters. Generate one locally using:

```powershell
backend/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep that value private. Do not commit `.env`. `COOKIE_SECURE=false` is for local HTTP development only; non-development configuration requires HTTPS and secure cookies.

Start the API:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open [CareCircle](http://localhost:5173) and [API documentation](http://127.0.0.1:8000/api/docs). Use `localhost:5173`, matching the configured origin. Create accounts through the UI; there are no default credentials. On macOS/Linux use `python3.12` and `.venv/bin/python` instead of the Windows executable paths.

After dependencies and database configuration are ready, Windows users may run `./scripts/start-local.ps1` from the repository root to apply migrations and launch both servers. Stop those servers with `./scripts/stop-local.ps1`. The script optionally supports an existing workspace-only MySQL runtime; it does not download a database or replace the setup above.

## Verification

From `backend`, run `.venv/Scripts/python.exe -m pytest`. For integration tests, first create a separate disposable MySQL 8.4 database named `carecircle_test` and configure its dedicated credentials in `.env.test`, using `.env.test.example`. Tests delete application rows only in the guarded test database. Without `TEST_DATABASE_URL`, database tests are explicitly skipped.

From `frontend`, run `npm run build`. From the repository root, run `python scripts/check_foundation.py` to validate documentation links and feature ownership.

For browser tests, stop development servers, run the backend MySQL tests once to apply test migrations, then from `frontend`:

```powershell
npx playwright install chromium
npx playwright test
```

Alternatively, on Windows with Edge installed, set `$env:E2E_BROWSER='msedge'` and run `npx playwright test`. Browser tests start temporary servers against the test database. Do not run browser and backend database tests simultaneously. Local evidence: **36 backend tests passed, 2 browser tests passed, frontend build passed** on 4 November 2026. Details and limitations are in [VALIDATION.md](VALIDATION.md); the hosted CI run must be checked after pushing.

## Team and delivery

Sprint 1 is due **8 November 2026**, with five assessed features across the team: Sandip CC-01; Tanjila CC-03/04; Tasin CC-06; Saif CC-12. Later deadlines and all twenty feature assignments are documented in [the sprint plan](docs/sprints.md) and [acceptance criteria](docs/features.md).

Significant packages and data sources must be recorded in [dependencies](docs/dependencies.md). Each member remains responsible for reviewing, testing and understanding their contribution.
