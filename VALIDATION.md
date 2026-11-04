# Validation performed — 2026-11-04

Environment: Windows, Python 3.12.14, Node 24.22.1, isolated MySQL Community 8.4.13, installed Microsoft Edge for browser tests. Synthetic accounts only; no XAMPP database changes.

| Check | Result |
|---|---|
| Python dependency resolution/install in isolated local environment | Passed; exact installed versions saved in backend/requirements.lock.txt |
| `python -m pytest -q -x --tb=short` from backend | **36 passed**; 18 contract/HTTP tests and 18 real MySQL scenarios covering authentication, consent, role/scopes, expiry/revocation, isolation, concurrency, cross-session CSRF, disabled accounts, privilege injection and transaction rollback |
| `npm run build` from frontend | **Passed**; TypeScript check and Vite production build |
| `alembic upgrade head` and `alembic check` | Passed on development MySQL; no model/schema differences. Tests also migrate an initially empty dedicated MySQL test database |
| `npx playwright test` with E2E_BROWSER=msedge | **2 passed**: full browser registration/profile/invite/accept/edit/revoke/logout workflow, plus desktop/mobile login layout |
| Screenshot inspection | Reviewed patient circle, caregiver mobile, desktop login and mobile login; no horizontal overflow at 390px in browser checks |
| `scripts/start-local.ps1` | Passed using installed Node 24.15.0; migrations applied and development API/frontend started. The earlier build/browser runs used bundled Node 24.22.1 |
| `python scripts/check_foundation.py` | Passed; local Markdown links and all 20 unique feature-owner assignments |

Known warning: the installed Starlette TestClient emits a deprecation warning for httpx and suggests httpx2. Tests pass; this is recorded, not silently hidden. Revisit in a dependency-maintenance PR with compatibility checks.

The first restricted API-test run stalled when Windows could not create a local event-loop socket; rerunning with local socket access passed. That was a test-environment issue, not evidence of working application features.

Not implemented/tested: assessed CC-02–CC-20 workflows, scheduler, email delivery/verification, password recovery, OCR, risk evaluation or production deployment. Migration downgrade is destructive and has not been run on development data. Hosted Linux CI has not run yet; no claim is made that local tests establish production security or medical suitability.

The first browser attempt failed on an exact label selector (required-field label markup); corrected accessible-role selectors passed. A resumed test attempt found the local MySQL process stopped; restarting it yielded the passing database run. Neither failure was hidden as feature completion.

The frontend currently emits a bundle-size advisory around 500 kB; code splitting can be introduced as future views are added. This is not a build failure. Dependencies/config/database files are local and ignored. The GitHub handoff folder contains the same application and test source; its documentation and packaging were reorganized on 5 November 2026.
