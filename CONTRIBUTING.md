# Team workflow

1. Pull latest main, inspect the working tree, and read README.md, docs/status.md and your responsibilities in docs/team.md. Start `feature/<name>/cc-XX-short-description` (shared setup: `foundation/<name>/<topic>`).
2. Work in small increments. Keep unrelated user edits. Never force-push shared branches or invent another member's commits.
3. Before a shared-contract change, open a PR explaining the affected consumers. Tag the relevant teammates by their real GitHub handles once known; do not invent handles or CODEOWNERS identities.
4. Merge foundation PRs in this order: shared schema/auth identity agreement; initial database migration; permissions/alert contracts implemented; prescription/scheduling/adherence integration. UI and isolated algorithm tests can proceed concurrently.
5. Before merging a migration, Tanjila checks latest main, assigns/rebases its `down_revision`, and verifies `alembic heads` has one head. Never rewrite a migration already applied by teammates. Run upgrade on an empty MySQL 8.4 database and the preceding version with sample data. Downgrades must document any loss.
6. Run backend tests, frontend build, and relevant MySQL integration tests. A passing infrastructure test is not evidence that a feature works.
7. PR description: feature ID, behavior, schema/contracts changed, test commands/results, screenshots using synthetic data, known limitations, and next integration step.
8. One teammate reviews the PR; discuss breaking interfaces with both producer and consumer. Do not block harmless local changes on unnecessary approval. Update status only with evidence.
9. Each student makes their own meaningful commits and pushes even incomplete work by the sprint end, labeled honestly. Add faculty as collaborator in Sprint 1; do not publish private spreadsheets/SRS access links.

## Definition of done

A feature is complete only when its acceptance criteria in docs/features.md work through UI + controller + service + MySQL persistence; access controls and invalid/boundary cases pass; dependencies integrate; relevant tests pass; limitations are documented; the owner can trace and modify the code. ML additionally records dataset provenance, evaluation, and limitations. Report generated-on-synthetic-data results as demo results, not real-world accuracy.

## First integration demonstration

Synthetic patient invites caregiver -> caregiver confirms a printed prescription -> scheduled dose -> patient marks taken -> stock and adherence update -> another dose misses its grace window -> one deduplicated alert -> authorized caregiver acknowledges -> analytics reflects the same events. Separately prove a second patient's caregiver cannot view or change any of this patient's data.

## Shared implementation conventions

- Preserve the selected architecture: React views, FastAPI controllers, Pydantic validation, SQLAlchemy models and services containing business rules. OCR/risk belong inside the same backend.
- `backend/app/schemas/contracts.py` defines shared payload types; `docs/contracts.md` defines their business meaning. Keep code, documentation, consumers, examples and tests synchronized when changing an interface.
- Reuse existing entities and services. Do not create parallel user, patient, medicine, dose or alert tables. Protocol declarations are not implemented workflows; mark missing integrations as blocked or partial instead of returning fabricated success.
- Perform patient authorization on the backend for every relevant read/write/download. Filter collection queries in the database. Derive actor identity and recipients from trusted server state, never browser-supplied privileges. Admin status does not bypass patient consent.
- Use synchronous SQLAlchemy sessions with plain `def` routes for blocking database work. Give each request/job its own session. The caller owns the transaction; shared services may flush but must not commit independently.
- Use Alembic migrations only, one shared revision chain and real MySQL integration tests. Do not call `create_all()` at application startup, reset existing databases or rewrite applied revisions.
- Use UUID identifiers, timezone-aware timestamps, UTC persistence and IANA patient timezones. Pass `now` into time-dependent rules so tests can control it.
- Background scheduling belongs in Tasin's separate worker, not each web-server process. Persist pending work and deduplication state; recheck recipient access immediately before delivery. Delivery must not be performed inside a clinical transaction.
- Reuse the frontend API client and MUI components. Keep JWTs out of browser storage. Keep secrets, private health data and raw invitation/session tokens out of logs, commits, fixtures and screenshots.
- Use explicit test doubles only in tests or clearly labeled development views. Never ship allow-all authorization, hardcoded patient identities or invented prediction results to conceal a missing dependency.
- Coordinate changes to frameworks, paid services, external processing of health data or packages that replace assessed workflows. Lock and test dependencies; document purpose, license and data provenance.

## Review and evidence

Test normal, invalid, boundary, unrelated-patient, repeated-request and concurrent-update cases where applicable. Report the commands actually run and their outcomes. Update implementation status, sprint records and dependency/AI-use records with real evidence; do not fabricate Git history, test results or review/approval records.

Every member owns the model, controller, service, interface and relevant tests for their features. Shared infrastructure ownership does not transfer all frontend/backend implementation to one person. Each contributor must understand and be able to explain and modify their submitted code during the viva.
