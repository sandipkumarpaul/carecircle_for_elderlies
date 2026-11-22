# Saif – Sprint 2 implementation notes: CC-14 Appointment Tracker

## What was implemented

**CC-14** – Appointment tracker and visit follow-up. Patients and caregivers with the
`appointments:write` scope can schedule appointments with a clinician label, location,
timezone, notes and a pre-visit checklist. Each checklist item can be ticked individually.
Appointments can be marked completed (which optionally queues a post-visit prescription
prompt) or cancelled with an optional reason. Cancelled appointments produce no reminders.
The post-visit prompt can be dismissed once it has been acted on.

## Files added / changed

| File | What it does |
|------|--------------|
| `backend/app/models/appointments.py` | `Appointment` SQLAlchemy model (new) |
| `backend/app/schemas/appointments.py` | Pydantic input schemas with IANA timezone validation (new) |
| `backend/app/services/appointments.py` | Business rules: create, update, checklist toggle, complete, cancel, post-visit prompt, reminder helper (new) |
| `backend/app/controllers/appointments.py` | 8 FastAPI routes under `/api/v1/patients/{id}/appointments` (new) |
| `backend/app/models/__init__.py` | Added `Appointment` to public import |
| `backend/app/main.py` | Registered `appointments_router` |
| `backend/migrations/versions/0007_saif_appointments.py` | Additive Alembic migration extending `0006_tanjila` (new) |
| `backend/tests/test_saif_s2_mysql.py` | 30 pytest cases covering schema, MySQL workflows and scopes (new) |
| `frontend/src/views/appointments/AppointmentView.tsx` | React view: schedule, checklist, complete/cancel, post-visit prompt, filter, pagination (new) |
| `frontend/src/App.tsx` | Mounted `AppointmentView` after `VitalsView` |
| `frontend/tests/appointments.spec.ts` | Playwright browser workflow (new) |

## Integration points respected

- **Migration chain**: `0007_saif_appointments` sets `down_revision = '0006_tanjila'`; one Alembic head. `alembic check` passes after upgrade and downgrade+upgrade.
- **Permission service**: every route calls `permissions.require(...)` with `appointments:read` or `appointments:write`. Patient row locked before writes (same pattern as Sandip's circle routes and my Sprint 1 vitals).
- **Alert service**: reminder helper uses `AlertService.raise_alert(...)` with `RaiseAlertCommand` and deduplication via `dedupe_key`.
- **Audit**: uses `circle.audit(...)` for create, update, complete, cancel, checklist update and prompt dismiss.
- **Shared session**: service flushes, controller commits — same contract as all other features.

## API routes

| Method | URL | What it does |
|--------|-----|--------------|
| GET | `/patients/{id}/appointments` | List appointments, filterable by status, paginated |
| POST | `/patients/{id}/appointments` | Schedule a new appointment |
| GET | `/patients/{id}/appointments/{appt_id}` | Get one appointment |
| PATCH | `/patients/{id}/appointments/{appt_id}` | Edit a scheduled appointment |
| PATCH | `/patients/{id}/appointments/{appt_id}/checklist/{idx}` | Toggle one checklist item |
| POST | `/patients/{id}/appointments/{appt_id}/complete` | Mark completed, optionally queue post-visit prompt |
| POST | `/patients/{id}/appointments/{appt_id}/cancel` | Cancel with optional reason |
| POST | `/patients/{id}/appointments/{appt_id}/dismiss-prompt` | Dismiss the post-visit prescription prompt |

## Verification

- 30 backend MySQL tests: `pytest backend/tests/test_saif_s2_mysql.py` — all pass.
- Full suite: `pytest backend/` — 185 passed, no regressions.
- `alembic upgrade head` and `alembic check` pass. Downgrade/upgrade round-trip passes.
- Playwright browser test: schedules with checklist, ticks item, completes with post-visit prompt, dismisses prompt, cancels second appointment, filters by status, checks persistence and mobile layout — 1 passed.
- `npm run build` passes (pre-existing chunk-size advisory only).

