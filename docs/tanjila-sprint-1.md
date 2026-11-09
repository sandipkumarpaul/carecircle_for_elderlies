# Tanjila — Sprint 1 implementation and handoff

CC-03 (medicine reference) and CC-04 (interaction warnings) extend Sandip's CC-01 and authentication. OCR (CC-02) and prescription revision/stop/history workflows (CC-05) remain later work.

## Setup and demonstration

1. Follow the root README, including `alembic upgrade head`. Migration `0002_tanjila` follows `0001_sandip`; it backfills existing patient allergies with an empty list and preserves identity/circle data.
2. Register an account normally. A database operator can grant reference administration, from `backend`, with `.venv/Scripts/python.exe -m app.reference_admin your-registered-email@example.com`. Add `--revoke` to remove it. On Linux/macOS use `.venv/bin/python`. Refresh the browser afterward. There is no default admin/password and registration cannot grant this privilege. Admin status grants no patient access.
3. Under Reference administration, choose `backend/data/medicines-demo.csv`, then Validate and import CSV. Repeat to show duplicate skipping. Change a row's strength to `invalid` to demonstrate an atomic rejected import with row errors.
4. Search `Dmo Alpha` to demonstrate fuzzy matching; filter `10 mg` and tablet. Find generic alternatives returns only the exact normalized generic, across brands/strengths. Alternatives are catalogue matches, not substitution advice.
5. For an interaction demonstration, select Demo Alpha as rule A and Demo Beta as rule B. Enter severity warning, explanation `Fictional interaction for the course demonstration`, and source `CareCircle synthetic teaching rule; not clinical`. Save the rule. No real drug interaction is asserted by this example.
6. Create/select your patient profile. Save `Demo compound beta` under reported allergies. Choose Demo Alpha, enter an explicit start date and local times, add to proposed list, check, then confirm.
7. Propose Demo Alpha Alternate and Demo Beta together. The check compares them with the earlier record and shows duplicate, allergy and interaction warnings, each with severity/source. Confirm stays disabled until every warning is acknowledged.
8. Save and refresh: the records persist. A caregiver with medicines:read can view them but cannot change them; revoking access blocks subsequent requests.

## MVC and request flow

- View: `frontend/src/views/medicines/MedicineView.tsx` uses the shared cookie/CSRF API client and patient selection. It supports CSV file selection/text, catalogue filters, generic alternatives, administration, allergies, proposed items and per-warning acknowledgement.
- Controller: `backend/app/controllers/medicines.py` derives the verified actor, checks reference administration or patient medicine scopes, locks shared state for writes and owns the transaction.
- Service: `backend/app/services/medicines.py` validates/deduplicates imports, ranks search results, evaluates warning rules and persists confirmation atomically.
- Models: `backend/app/models/medicines.py` defines reference, prescription/item and warning-review records. `Patient.allergies` holds normalized reported generic names. `schemas/medicines.py` validates feature requests; canonical dose inputs still use `PrescriptionItemInput`.

Import identity is a SHA-256 key of normalized generic, brand, strength and form. Unicode NFKC/case/whitespace are normalized; numeric strength spacing is removed. No strength conversion or clinical equivalence is inferred. All rows must validate before insertion. Reimport skips existing identities and preserves their original provenance. The CSV has six mandatory columns, a 500-row limit and a 500,000-character request limit. A malformed or empty file reports errors without changing reference rows. Form determines the accepted dose unit.

Search uses substring matching followed by Python standard-library sequence similarity (threshold 0.60), stable tie ordering and pagination. It scans the reference catalogue and is intended for a small course dataset; a large production catalogue needs indexed candidate selection. No patient data enters search ranking.

Rules match their referenced generic pair across brands and strengths. Proposed/proposed and proposed/current-or-upcoming items are compared when their inclusive date ranges overlap. A same-generic pair raises a duplicate warning. Allergy checks are exact normalized generic-name matches to patient/caregiver reports; class allergies, synonyms, multi-ingredient parsing, pharmacological inference and comprehensive clinical coverage are not implemented. Date overlap is conservative by calendar date, not a pharmacokinetic model.

## Warning review and concurrency

The server stores the proposed items and warning snapshots in `warning_checks`, bound to patient and actor, expiring after 15 minutes. Confirmation accepts only the saved check ID and the exact set of acknowledged warning IDs. It recalculates state and rejects changes to allergies, active records, reference data or expiry. The client cannot replace checked items at confirmation. A repeated confirmed check returns its original version instead of duplicating medicines; it still requires current medicine-write permission and the original acknowledgement set.

A singleton `reference_revision` row serializes reference updates and warning checks/confirmation. Patient-row locking serializes patient changes and confirms against current permissions. Lock order is reference first, then patient. Each controller commits once; errors roll back. Acknowledgement time and actor are persisted with warning provenance; audit events contain identifiers/actions, not raw clinical content.

## Integrated dose scheduling (9 November 2026)

Initial CC-04 confirmation calls the real ScheduleService.regenerate after flushing the version and items, inside the same transaction. Failures roll back both medicine and dose records. Successful confirmations return schedule_status=generated; retries return the original version and its stored status. Upcoming doses appear under Recorded medicines.

Existing pre-integration records remain valid. Refresh dose schedule generates only future doses and extends the rolling horizon; it does not change the original confirmation date or replay elapsed doses. Read-only caregivers can view doses but cannot refresh them. CC-05 revision/stop/history remains future work. See [Tasin’s guide](tasin-sprint-1.md).
