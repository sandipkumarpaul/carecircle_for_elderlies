# Tasin — CC-06 dose schedule integration

Current update: CC-02 OCR and CC-05 revision/stop/history are implemented in [Tanjila Sprint 2](tanjila-sprint-2.md). Statements below about these being future work describe this earlier handoff.


The 9 November integration places Tasin's uploaded modules in their application paths and connects them to Tanjila's medicine confirmation. Original GitHub base: 6527df4, following Saif's 5dafa52 and Tanjila's a94f364.

## MVC and transaction flow

- Model: `backend/app/models/doses.py`; unique item/time constraint prevents duplicate events. Migration `0004_tasin` extends `0003_saif` without altering existing records.
- Controller: `backend/app/controllers/doses.py`; verified actor, medicine read/write scopes, patient lock, pagination and transaction completion.
- Service: `backend/app/services/schedules.py`; explicit local times become UTC events through today plus 13 days. End date is inclusive; as-needed items generate none. DST overlap uses the first occurrence; a nonexistent time moves forward by the DST gap.
- View: `frontend/src/views/medicines/DoseSchedule.tsx`; upcoming doses, original item timezone, quantity, instructions, pagination and explicit refresh.
- Confirmation: `services/medicines.py` calls regeneration before commit. A failed generation rolls back the prescription and warning confirmation. Retrying a confirmed check returns its existing version.

All production callers acquire the same patient lock before generation. Refresh, confirmation and concurrent refreshes therefore serialize, with the unique database constraint providing additional protection. Services flush but never commit independently.

## Demonstration

1. Apply `alembic upgrade head`, sign in and select a patient you can manage.
2. Use Tanjila's medicine workflow to confirm a fixed-time record starting tomorrow, with two explicit times and an end date two days later.
3. Upcoming doses shows six events in the record's timezone. Reload to verify persistence.
4. Click Refresh dose schedule twice. The same events remain, without duplicates.
5. Confirm an as-needed record: no automatic doses are added for that item.
6. A caregiver with View medicines can see doses; Manage medicines is required to refresh. Revoke access and reload: the records are inaccessible.

## Existing records and daily extension

The migration does not rewrite existing medicine records. Refresh dose schedule fills their future horizon and marks them generated; past times are never replayed. Records whose start date is beyond the current horizon will initially have zero events and acquire events on later refreshes.

Run `python -m app.refresh_schedules` from backend with normal database settings for a daily, one-shot extension across patients. Arrange daily invocation with an operating-system scheduler when running continuously. The UI supports manual extension; no background task is installed automatically.

Generated means the current horizon was processed, not that a reminder was sent. Reminder/confirmation, snoozing, missed-dose escalation and prescription revision/stop screens are later features. Existing taken/skipped/missed history is not changed by schedule regeneration. No automatic completion or adherence result is inferred.
