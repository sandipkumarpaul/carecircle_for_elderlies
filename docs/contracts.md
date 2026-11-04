# Shared interfaces and API rules — v1

**Implementation status:** health, auth (csrf/register/login/logout/me), patient create/list/detail, care-circle read, invite create/revoke/preview/accept, and member access edit/revoke are implemented. Open `/api/docs` for the actual route/request definitions. Other routes below remain design targets. Shared types live in `backend/app/schemas/contracts.py`; identity requests in `schemas/identity.py`; concrete permission/alert services in `services/access.py` and `services/alerts.py`.

Invite preview/accept use `POST /api/v1/circle/invites/{preview,accept}` with a token in the JSON body. The copyable link holds it in a URL fragment so it is not sent in access logs. Creation returns the private link once; raw tokens are not persisted. The invitee must sign into the matching email and explicitly accept. No invitation email transport or email verification is claimed: the inviter manually shares the secret link with the intended person.

Patient creation accepts `kind=self|dependent`, display name, timezone, `consent=true` and a consent/representation statement. Self profiles are unique per account; dependent profiles have the creator as their primary caregiver. Patient owner controls primary appointment/removal; primary caregivers can manage only secondary access within their own scopes. Secondary scopes cannot contain circle/privacy management. Removing one's own membership is intentionally rejected to avoid orphaning a dependent profile. Patient ownership transfer/recovery is a future workflow.

Auth and circle writes use transaction-backed uniqueness/state rules rather than the later domain `Idempotency-Key` contract. Duplicate acceptance returns 409. Future dose/stock writes still require durable request idempotency as specified below. Member scope changes invalidate their pending invitations and suppress queued deliveries; revocation also removes immediate read/list access.

## HTTP conventions

- `/api/v1`; JSON snake_case; UUID strings; ISO-8601 timestamps with UTC `Z` or explicit offset; dates `YYYY-MM-DD`.
- Single success: resource directly; lists: `{items: [...], total: 0, offset: 0, limit: 20}` with limit 1–100 and stable `(created_at,id)` ordering.
- Errors: `{error: {code: string, message: string, details: []}}`; 401 unauthenticated, 403 authenticated but forbidden, 404 inaccessible object lookup (avoid patient enumeration), 409 state/idempotency conflict, 422 invalid input. Do not echo passwords, uploaded bytes, raw tokens or validation input in errors.
- POST create 201; GET/PATCH/action success 200; DELETE/logout 204. No destructive GET.
- Unsafe writes use cookie auth + server-validated CSRF header. Durable externally retried actions use `Idempotency-Key` UUID header mapped into internal command schemas. Same key+same payload returns original result; same key+different payload is 409. Scope keys by patient and operation. Persist canonical payload hash; frontend reuses key on retry.
- Browser cannot choose trusted `actor_user_id`, patient ownership, notification recipients, or worker-only action `missed`. Controllers derive actor from verified session; worker uses an explicit internal system context.

## 1. Permission check (Sandip -> all)

`require(session, actor_user_id, patient_id, scope) -> None` raises forbidden/not-found if not allowed. Current ownership or accepted non-revoked membership plus scope is required every request. Admin is not a patient-data bypass. Resolve target entity and verify its `patient_id` matches URL context. Collection queries must apply authorization filters at DB query time. Recheck consent before background notifications and private exports. Test revoked, pending-invite, unrelated-circle, and allowed patient/primary/secondary cases.

## 2. Alert creation (Sandip <- Tasin/Saif/Tanjila)

`raise_alert(session, command: RaiseAlertCommand, now) -> UUID` is implemented for non-SOS types and returns an existing or newly created alert ID. The trusted calling service must verify that its source entity belongs to the patient before invoking it; those clinical source tables do not exist yet. Command has patient, type, severity, source_type/id, and stable dedupe_key. It does not accept arbitrary recipients. Service derives authorized recipients and creates alert/recipient/in-app delivery records in caller's transaction. It validates type/source pairing and rejects reuse of a dedupe key with a different payload. No SMTP call or public feed exists yet; a browser cannot invoke arbitrary alert creation. SOS is explicitly rejected until CC-16 consent and emergency logic exist. `delivery_allowed` rechecks current recipient access and must be used by Tasin before dispatch; he owns actual delivery, retries and quiet hours.

Types: missed_dose, vital_threshold, vital_trend, low_stock, stock_reconciliation, sos, checkin_missed, prescription_changed, possible_side_effect, adherence_risk, task_due. Dedupe key examples: `missed_dose:<dose_uuid>` and `vital_threshold:<reading_uuid>`; escalation stages create delivery records for the same alert, not duplicate feed entries. State is open -> acknowledged -> resolved (resolve may also directly close open). Acknowledgement of one alert by an authorized caregiver stops its escalation. Worker rechecks state immediately before each send. Critical SOS bypasses quiet hours; other email sends defer to quiet-hours end while feed remains visible. Never silently suppress SOS in quiet hours.

## 3. Prescription and schedule regeneration (Tanjila <-> Tasin)

`PrescriptionItemInput` fields are medicine_id, quantity_per_dose, unit, start_date, end_date?, schedule_kind, times_local, timezone, meal_relation, instructions?. Times are explicit `HH:MM`, unique, sorted. Fixed schedules require 1–6 times/day; as-needed schedules require none. Quantities >0 with <=3 decimal places; end >= start; timezone is validated IANA. `effective_from` in `RegenerateScheduleCommand` is an aware instant, not a date.

Tanjila confirms a draft as an immutable version, closes the preceding version, and calls `regenerate(session, command, now)` in the **same transaction**. Command identifies patient, prescription root, previous version (nullable), new version (nullable when stopping), and effective instant. Tasin validates all IDs belong together, cancels pending/unconsumed future events at/after effective instant from the previous version, and generates the new horizon. Preserve taken/skipped/missed history and events before the cutoff. Reject a retroactive effective time in v1; corrections to history require a separate audited workflow. A uniqueness constraint prevents duplicate regeneration.

Generate a rolling 14-day horizon, extended daily; end_date is inclusive in patient's local calendar. Start/end and timezone belong to immutable item versions. For DST ambiguity use first occurrence (`fold=0`); for nonexistent local time move forward by the DST gap; test both. Patient timezone changes do not rewrite existing items/events: create a revised prescription schedule explicitly. As-needed items do not generate scheduled events; manual as-needed logging can be a later, separately defined extension.

## 4. Adherence log (Tasin -> Saif)

`record(session, command: RecordAdherenceCommand, now) -> UUID` returns immutable log ID. Internal command identifies patient, event, verified actor (nullable only for system missed), action, occurred_at, idempotency_key. For v1 patient-reported occurred_at must be within the previous 24 hours and no later than server now; retain recorded_at=now. More distant corrections require audited follow-up work, not hidden backdating.

Actions taken/skipped/snoozed/missed; current event states pending/taken/skipped/missed/cancelled. Pending accepts taken/skipped/snoozed or worker missed. Missed accepts late taken/skipped. Taken/skipped cannot transition again in v1. Snooze increments counter and stores snoozed_until while event remains pending; max 2 snoozes of 10 minutes, never beyond the original 30-minute grace deadline. No confirmation before scheduled_at in v1. Use row lock and one transaction for log, projection, and stock movement. Same idempotency key returns same log; a different duplicate terminal action is 409, not another stock deduction.

Analytics period is `[start,end)` based on scheduled_at. Eligible denominator: non-cancelled fixed-dose events scheduled in period whose grace_until <= as_of. Adherence = eligible events currently taken / eligible count; skipped/missed count in denominator; zero eligible returns null (UI: No doses due). On-time adherence separately requires taken occurred_at <= grace_until. Exclude future/unmatured, cancelled, as-needed events. Late confirmations may change historical adherence; missed logs remain for explanation. Risk uses only information strictly before prediction time and cannot use later outcome labels as inputs.

## Scheduler defaults (Tasin)

One worker ticks every 30 seconds, scans durable due rows, leases work in MySQL and retries failures with 1/5/15-minute delays, then marks failed visibly. Unique keys protect database effects; email is at-least-once because a crash after SMTP acceptance can cause resend. Do not claim exactly-once email. Grace 30 minutes; at deadline mark missed and re-remind patient, after 10 more minutes alert primary caregiver, after 10 further minutes alert permitted secondary caregivers until acknowledged. SOS immediately targets authorized caregivers; if unacknowledged after 5 minutes notify the configured emergency contact through the supported email channel. No claim of ambulance dispatch/SMS. Daily check-in defaults 09:00 patient local +60-minute grace; weekly digest Monday 09:00 patient local. Thresholds/times configurable per patient in later settings; these defaults are application demo rules, not medical advice.

## Reserved route map

All patient-scoped paths below are under `/patients/{patient_id}`. Each owner implements GET list/detail and explicit state-changing POST/PATCH routes as appropriate, following this naming rather than inventing parallel APIs.

| Owner | Routes / intended operations |
|---|---|
| Sandip | `/auth/{register,login,logout,me,csrf}`; `/patients`; patient `/circle`, `/circle/invites`, `/circle/members/{id}` (revoke); `/alerts`, `/alerts/{id}/acknowledge`, `/alerts/{id}/resolve`; `/sos`; `/tasks`, `/tasks/{id}/claim`; `/audit`; `/privacy/exports`, `/privacy/erasures` |
| Tanjila | global `/medicines`, `/medicines/import` (admin); patient `/prescription-documents`, `/prescription-documents/{id}/ocr`, `/prescriptions`, `/prescriptions/{id}/versions`, `/prescription-versions/{id}/confirm`, `/prescriptions/{id}/stop`; `/interaction-check`; `/symptoms` |
| Tasin | `/doses`, `/doses/{id}/responses`; `/stocks`, `/stocks/{id}/refills`; `/checkins/today`, `/checkins/today/respond` |
| Saif | `/vitals`, `/vital-thresholds`; `/appointments`, `/appointments/{id}/complete`; `/analytics/adherence`; `/risk`; `/summaries`, `/summaries/{id}/shares`; public token-limited `/shares/{token}` outside patient prefix |

Service interfaces are internal calls, not extra HTTP endpoints. Final request/response schemas for feature-specific routes are added to runtime OpenAPI in each owner PR. `/risk` GET reads existing predictions, it does not train on every request.

## Examples and dependency handoff

`backend/tests/fixtures/contracts.json` contains validated, explicitly synthetic examples for all four data commands. These UUIDs are fixture identities, not real production IDs or existing database rows. Permission example: `require(session, verified_user.id, patient.id, Scope.MEDICINES_READ)` returns None on success and must fail for a revoked/unrelated membership. The Protocols do not implement that behavior.

| Producer | Consumer | Ready-to-integrate handoff |
|---|---|---|
| Sandip | Everyone | Verified session actor + `require`; cross-patient/revoked tests passing |
| Sandip | Tanjila/Tasin/Saif | `raise_alert`; durable records and duplicate-key behavior |
| Tanjila | Tasin | Confirmed immutable prescription items; shared transaction and regeneration command |
| Tasin | Tanjila | `regenerate`; cutoff/horizon/stop/retry tests |
| Tasin | Saif | Dose projection + immutable adherence logs + agreed denominator fixtures |
| Saif | Tasin | Persisted risk score/model version; optional earlier reminder only when score >=0.70, 15 minutes before due; no model means normal reminders only |
| Tasin | Everyone | Notification worker and delivery status; no owner sends SMTP inline |

Alert authorization requires both `alerts:read` and the source domain's read scope for sensitive details; recipients lacking that domain scope receive no clinical content. SOS health-card disclosure requires explicit emergency-sharing consent; location also requires location consent and recipient scope. Summary creation includes only domains the creator may read, and records that scope set in the snapshot metadata; a share cannot expand it.

## Uploads and sharing

Prescription upload: JPEG/PNG only in v1, <=10 MiB and <=20 megapixels; inspect decoded content, reject unsupported formats and decompression bombs; sanitize names and store generated keys privately. OCR has bounded execution time, returns draft suggestions/confidence, and cannot confirm prescriptions automatically. No external OCR upload service. Summary shares use >=256-bit cryptographically random tokens, stored hashed, default 24-hour expiry, revocable; check expiry/revocation on every access. Serve prepared minimal summary only with Cache-Control: no-store and audit access; no token in analytics/logs.
