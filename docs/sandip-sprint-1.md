# Sandip — Sprint 1 handoff

Deadline: **8 November 2026**. Assessed feature: **CC-01 Care circle and consent access**. Authentication, the initial identity migration and alert persistence are supporting work and do not add to the feature count. The team's Sprint 1 target is five features total; the other four belong to Tanjila, Tasin and Saif.

## What is implemented

- Registration, login, logout, normalized unique email, Argon2 password hashes and an eight-hour session.
- JWT is held in an HttpOnly cookie. The server also checks a revocable database session. Session-bound CSRF headers and exact-origin checks protect writes; persistent per-IP and per-email counters limit authentication attempts.
- Users can create one personal patient profile and additional dependent profiles with a recorded consent/authority statement. A dependent creator becomes primary caregiver; an assertion does not verify legal authority.
- Patients invite a primary or secondary caregiver with explicit scopes and expiry (1–168 hours, default 48). A primary caregiver can invite only secondary caregivers within their own access.
- A new random secret link is shown once for manual sharing. The database stores only its hash. The signed-in matching account reviews and accepts the invitation with explicit consent. Expired/revoked/already-used links fail.
- Patients control primary appointment/removal; secondary caregivers cannot administer the circle. Scope edits apply immediately. Revocation removes backend access, invalidates pending invitations created by that caregiver and suppresses pending delivery rows.
- Shared `PermissionService.require` and `AlertService.raise_alert` are ready for other members. Alerts are internal persistence only; sources must be validated by the calling feature. Recipients require both alert and source-domain read permission. Tasin must recheck `delivery_allowed` before dispatch.
- Migration `0001_sandip` contains the identity/circle/audit/alert subset, not the entire future database.

## Run locally

Follow the fresh-clone setup in [README.md](../README.md): create your own MySQL development/test databases, install dependencies, configure private environment files and apply migration 0001_sandip. No credentials or database runtime are included. Once configured, use the two terminal commands or the Windows startup/shutdown scripts. The application has no default login accounts; register through the UI.

## Manual demonstration

1. Create a patient account in one browser window and a caregiver account with another email in a separate browser profile/private window.
2. As patient, create a personal profile, record consent, and invite the caregiver email with View medicines and View vitals. Copy the displayed link privately.
3. As caregiver, paste/open the link, review the patient/role/scopes and accept. The circle appears, but its management controls do not.
4. As patient, edit access to remove View vitals. Refresh the caregiver window: the scope disappears. Demonstrate the server-side permission tests rather than claiming future medicine/vitals screens exist.
5. Revoke caregiver access. Refresh their page: the patient disappears; direct patient API access returns 404. The old invitation cannot be reused.
6. Repeat with a primary caregiver, showing that they can grant only permissions they hold and cannot appoint another primary.
7. Show the consent/audit rows and hashed invite/session/password records without exposing raw secrets. Show a failed unrelated-account request and the test results.

## Code walkthrough for the viva

| Concern | Main files | Explain |
|---|---|---|
| Model | backend/app/models/identity.py | Foreign keys, unique membership, UTC conversion, hashed secrets |
| Controller | backend/app/controllers/auth.py, circle.py, dependencies.py | Validation, authenticated actor, CSRF, route orchestration and transaction commit |
| Domain rules | backend/app/services/access.py, circle.py, alerts.py | Scope enforcement, patient-row locks, consent, expiry, single-use acceptance, recipient filtering |
| View | frontend/src/views/auth and views/circle | Forms, consent review, role/scope presentation, loading/error states |
| Database history | backend/migrations/versions/0001_sandip_*.py | Reproducible schema, one Alembic chain, no startup create_all |
| Evidence | backend/tests/test_sandip_mysql.py, frontend/tests/circle.spec.ts | Real database and browser tests; normal/invalid/concurrent cases |

Trace one invite from the button through the shared API client, authentication dependency, controller, service, row lock, SQLAlchemy record, commit, and returned link. Explain why cookies alone are not enough without CSRF and why hiding a button is not authorization. Be ready to add a test or change the expiry bound yourself. Student review/understanding is not asserted by generated code or passing tests.

## Handoff to teammates

- Tanjila: CC-03/04 now extend this baseline through `0002_tanjila`; see [Tanjila's handoff](tanjila-sprint-1.md). Continue reusing User/Patient and the existing DB/session dependency for later features.
- Tasin: notification deliveries currently hold minimal in-app pending records. Extend with retries/leases/channels, not a duplicate table. Implement schedule/adherence services and call permission checks and `delivery_allowed`.
- Saif: use the existing API client, signed-in session and patient scopes. Vitals must call `require(..., Scope.VITALS_READ/WRITE)` and validate source ownership before raising alerts.
- Every service must participate in the caller's transaction. Do not commit inside shared permission/circle/alert methods.

## Honest limits

No email sending/verification, password recovery/change, patient-ownership transfer, real clinical screens, notification worker or production deployment yet. Copy-link invitations are the chosen Sprint 1 delivery method. Admin does not gain implicit patient access. Self-removal of the sole primary is blocked to avoid orphaning dependent profiles; a transfer/recovery workflow is future work. No course spreadsheet/SRS submission, student commits, faculty approvals or teammate review have been fabricated.
