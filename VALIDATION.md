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
