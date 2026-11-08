# Saif – Sprint 1 implementation notes: CC-12 Vitals logging and trend alerts

## What was implemented

**CC-12** – Vitals logging and trend alerts. Patients and caregivers with the `vitals:write`
scope can record blood pressure, blood sugar, weight and SpO2 readings. Per-patient limits
can be saved for any kind; the server compares each new reading against those limits and
raises a `vital_threshold` alert when a reading is out of range. The backend also evaluates a
deterministic, fully documented trend rule each time a new reading becomes the newest one for
a kind; a worsening trend raises a `vital_trend` alert.

## Files added / changed

| File | What it does |
|------|--------------|
| `backend/app/models/vitals.py` | `Vital` and `VitalThreshold` SQLAlchemy models (new) |
| `backend/app/schemas/vitals.py` | Pydantic input schemas with plausibility and unit checks (new) |
| `backend/app/services/vitals.py` | All business rules: unit conversion, bound checks, trend rule, alert raising (new) |
| `backend/app/controllers/vitals.py` | FastAPI routes under `/api/v1/patients/{id}/vitals` and `/vital-thresholds` (new) |
| `backend/app/models/__init__.py` | Added `Vital`, `VitalThreshold` to public import |
| `backend/app/main.py` | Registered `vitals_router` |
| `backend/migrations/versions/0003_saif_vitals_and_thresholds.py` | Additive Alembic migration extending `0002_tanjila` (new) |
| `backend/tests/test_saif_mysql.py` | 69 pytest cases covering rules, schema, MySQL workflows and concurrency (new) |
| `frontend/src/views/vitals/VitalsView.tsx` | React view: log readings, set limits, view trends and reading history (new) |
| `frontend/src/App.tsx` | Mounted `VitalsView` after the medicine view |
| `frontend/tests/vitals.spec.ts` | Playwright browser workflow (new) |
| `frontend/playwright.local.config.ts` | Local sandbox Playwright config using bundled Chromium (new, not committed) |

## Integration points respected

- **Migration chain**: `0003_saif` sets `down_revision = '0002_tanjila'`; one Alembic head. `alembic check` passes after upgrade and after downgrade+upgrade.
- **Permission service**: every route calls `permissions.require(...)` with `vitals:read` or `vitals:write`. The patient row is locked before `vitals:write` operations (same pattern as Sandip's circle routes).
- **Alert service**: uses `AlertService.raise_alert(...)` and the shared `RaiseAlertCommand` schema from `app/schemas/contracts.py`. Alert recipients are determined by the existing permission service (only members with `vitals:read` or `vitals:write`).
- **Audit**: uses `circle.audit(...)` for `vital.recorded` and `vital_threshold.saved/deleted`. Raw measurement values are not stored in audit event text.
- **Shared session**: service flushes, controller commits — same contract as medicines.

## Documented trend rule

A worsening trend needs: (a) the last N readings within a window of W days all moving strictly in one direction with no equal or reversing step, and (b) a net change of at least M in the threshold's unit. Defaults: N=3, W=14 days, M varies by kind (10 mmHg for bp, 20 mg/dL for sugar, 2 kg for weight, 3% for SpO2). Worsening direction: blood pressure (systolic) and sugar rising; SpO2 falling; weight in either direction. A back-dated reading is never the newest and so never triggers the trend evaluation. Per-patient overrides can be set via the threshold API.

## Verification

- 69 backend MySQL tests: `pytest backend/tests/test_saif_mysql.py` — all pass.
- Full suite: `pytest backend/` — 115 passed, no regressions in Sandip's or Tanjila's tests.
- `alembic upgrade head` and `alembic check` pass. Downgrade/upgrade round-trip passes.
- Playwright browser test: logs readings, sees threshold and trend alerts, validates rejection, checks persistence and mobile layout — 1 passed.
- `npm run build` passes (pre-existing chunk-size advisory only).

## AI tool usage disclosure

GitHub Copilot / Claude: used to assist in generating boilerplate for model columns, Pydantic validators and test parametrize lists. All business logic (trend rule, unit conversion, bound evaluation, alert deduplication approach) was written and reviewed by me. I can explain, modify and defend every line in the viva.
