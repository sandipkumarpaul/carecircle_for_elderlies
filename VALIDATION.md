# Sandip Sprint 2 on whole-team Sprint 1 — 9 November 2026

This package copies the verified Whole_Team_Sprint1 increment and adds CC-18. No GitHub upload has been performed.

| Check | Result |
|---|---|
| Backend, real MySQL 8.4 test database | **141 passed**, no skips: 126 previous cases plus 15 CC-18 cases |
| Browser workflows, Edge | **All five passed**: existing four workflows passed in the combined run; the new alert-centre test passed after correcting an ambiguous test selector |
| Frontend TypeScript / Vite build | Passed after final UI changes |
| 0004_tasin → 0005_sandip populated migration | Passed; all predecessor identity, medicine, dose, vitals, alert/recipient and delivery rows preserved |
| Alembic schema comparison and heads | No new operations detected; single head 0005_sandip |
| Documentation/feature-ownership check | Passed |
| Mobile layout | 390px width, no horizontal overflow; alert-centre screenshot inspected |

CC-18 coverage includes severity/time ordering, status/severity/unread filtering, pagination bounds, personal read isolation, recipient membership, source scope removal, revocation, cross-patient access, CSRF, concurrent acknowledgement, idempotent timestamps/audits, direct resolution, cancellation of current and later escalation deliveries, personal settings, invalid quiet-hour input, overnight/daytime boundaries, DST gaps/overlaps and critical/in-app bypass. Browser verification creates a genuine alert through Saif's vitals feature, then reads, acknowledges, resolves and reloads it, including quiet-hour persistence.

All database checks use the dedicated disposable carecircle_test database. Existing preview data was not reset. The migration check temporarily downgrades/re-upgrades only the test database, comparing predecessor columns. Original Whole_Team_Sprint1 remains separate and unchanged. Private .env.test, dependency links, caches, build outputs and browser artifacts are excluded from this upload folder.

Known limits: SMTP sending and escalation workers are future integrations; quiet-hour behaviour is verified at the shared delivery gate, not by sending email. The feed refreshes on opening or manually. TestClient/httpx deprecation and Vite bundle-size advisories remain non-failing. Hosted Actions must be checked after manual upload.

---

## Historical whole-team Sprint 1 validation

The following records describe the predecessor increment.

# Whole-team Sprint 1 validation — 9 November 2026

Source: GitHub main 6527df4 (Tasin), including Saif 5dafa52 and Sandip/Tanjila a94f364. This folder contains local integration corrections; no remote push was made.

| Check | Result |
|---|---|
| Backend suite, real MySQL 8.4 test database | **126 passed**; no skips |
| Browser suite, Microsoft Edge | **4 passed**: care-circle permissions/revocation, responsive login, medicine warning/confirmation plus dose display/refresh/persistence, vitals workflow |
| Frontend TypeScript and Vite build | Passed |
| Populated 0003_saif → 0004_tasin migration | Passed; every existing user, patient, membership, prescription/version/item, vital and threshold row unchanged |
| Alembic model/schema comparison | Passed; no new operations detected; single head 0004_tasin |

New regression checks exercise atomic rollback on schedule failure, confirmation retries, duplicate-free concurrent refresh, legacy unscheduled records, rolling-horizon extension, inclusive end dates, local-to-UTC conversion, as-needed exclusions, read-only and unrelated-user denial, CSRF and revocation. Tasin's original six tests now run from backend/tests instead of being omitted at repository root.

Tests use only the separate guarded carecircle_test database; original preview data was not reset. Migration validation deliberately removed/recreated the new dose table in that disposable database, while comparing all predecessor records before/after. Local dependency links, private test configuration, build outputs and browser artifacts are excluded from this upload folder.

Known advisories: existing TestClient/httpx deprecation and Vite bundle-size warning; neither fails validation. Daily schedule extension must be invoked by an operator or configured operating-system scheduler. Reminders, medication-taking actions and full revision/stop workflows are not part of this integration. Hosted CI must be checked after upload; local success does not claim a new hosted run.

---

## Historical validation before whole-team integration

The following records describe the earlier Sandip/Tanjila snapshot, not the current implementation status.

# Local validation — combined Sprint 1, 5 November 2026

Environment: Windows, Python 3.12.14, Node 24.15.0, MySQL Community 8.4.13 and Microsoft Edge. Tests use synthetic accounts and the separate guarded `carecircle_test` database. Development data was not reset.

| Check | Result |
|---|---|
| Backend `python -m pytest -q` | **46 passed**: all 36 Sandip baseline tests plus 10 Tanjila MySQL cases (including parametrized stale-state cases) |
| Frontend `npm run build` | **Passed**: TypeScript and Vite production build |
| Browser `npx playwright test` with E2E_BROWSER=msedge | **3 passed**: existing circle lifecycle, login layout, and medicine import/allergy acknowledgement/persistence workflow |
| Mobile browser checks | No horizontal overflow at 390px; warning-review screenshot visually inspected |
| Upgrade from 0001_sandip to 0002_tanjila | Passed with synthetic existing patients; identity rows preserved and allergies backfilled |
| Fresh MySQL schema upgrade | Passed through both revisions; `alembic check` reports no model/schema differences |
| `alembic heads` | Single head: 0002_tanjila |
| `python scripts/check_foundation.py` | Passed: documentation links and 20 unique feature assignments |

New backend coverage includes atomic CSV row rejection, deduplication, fuzzy and exact-generic lookup, filters/pagination bounds, admin authorization, CSRF, unauthenticated and cross-patient access, read-only/revoked caregivers, interaction/allergy/duplicate warnings, acknowledgement persistence, stale/expired reviews, unknown medicines/invalid doses and concurrent retry producing one version.

The migration was exercised locally against both populated predecessor and empty test schemas. Its downgrade drops the added clinical/reference tables and allergy column, destroying their data; use only with a backup and deliberate rollback decision. The original 0001_sandip migration was preserved. No production database or deployment was tested.

Two issues found during verification were corrected: the new migration's generated downgrade attempted to drop foreign-key-supporting indexes before their tables (MySQL rejects that), and the browser test initially expected trailing decimal zeroes instead of checking the numeric quantity. Fresh/upgrade/schema checks and the final browser run passed after correction. The API now explicitly serializes quantities as decimal strings.

Known existing advisories: Starlette TestClient emits an httpx deprecation warning; Vite reports the main JavaScript bundle above 500 kB (about 518 kB uncompressed). Neither fails the checks. No dependency upgrades were made to hide these warnings.

The local sources were based on GitHub main `91b54a2ba4a840fbf7d8be583e89d19ac968b2b6`, fetched on 5 November. These results do not claim hosted CI has run for this combined update. After manual upload, check the repository's Actions run.

Not implemented: real clinical reference coverage, prescription OCR/revisions/stopping, schedule regeneration/dose reminders, SMTP, remaining assessed features, or production deployment. The medicine demonstration data/rule are fictional. Student review and individual viva preparation remain necessary.
