# Feature acceptance baseline

These are implementation targets, not completion claims. All features require patient authorization, invalid-input handling, persisted state and tests. Authentication is additional, not counted among the 20.

| ID | Owner | Feature | Minimum demonstrable acceptance criteria |
|---|---|---|---|
| CC-01 | Sandip | Care circle and consent | Expiring invitation accepted once; scoped primary/secondary access; revoke blocks subsequent reads/writes and delivery; unrelated user denied. |
| CC-02 | Tanjila | Prescription OCR | Printed JPEG/PNG yields editable medicine suggestions; user confirms/corrects; low-quality failure allows manual entry; no automatic clinical action; unauthorized/oversized upload denied. |
| CC-03 | Tanjila | Medicine reference | CSV validates identity/units/source/license, reports row errors, deduplicates import; search supports brand/generic/fuzzy matches and strength/form; repeat import adds no duplicates. |
| CC-04 | Tanjila | Interaction warnings | Compare proposed items against active medicines and allergies; flag same-generic duplicates; show rule source/severity; require recorded acknowledgement before confirmation when flagged; never claim all interactions covered. |
| CC-05 | Tanjila | Prescription revisions | Confirm new immutable version, preserve prior history, close effective interval, regenerate only future pending doses and notify authorized caregivers; rollback all changes if regeneration fails. |
| CC-06 | Tasin | Dose schedule | Explicit local times become unique UTC events in a rolling horizon, with inclusive end date and defined DST behavior; repeated generation creates no duplicates; as-needed creates no automatic event. |
| CC-07 | Tasin | Reminder/confirmation | Due reminder and taken/skipped/snoozed responses; grace/snooze limits enforced; late confirmation preserved; duplicate/concurrent confirmation cannot create duplicate stock effects. |
| CC-08 | Tasin | Missed-dose escalation | Grace expiry logs missed and starts staged chain; acknowledgement stops future sends; restart catches overdue work; duplicate ticks do not create duplicate alerts. |
| CC-09 | Saif | Adherence risk | Reproducible training/evaluation using past-only features and time split; bounded probability and model version; explicitly label synthetic training; high risk creates earlier reminder/flag without duplicate normal reminder; missing model shown as unavailable. |
| CC-10 | Saif | Analytics/digest | Same canonical denominator across charts/digests; test zero eligible, cancellation, skipped, late taken; weekly digest per authorized recipient once per period with retry tracking. |
| CC-11 | Tasin | Refill/stock | Taken consumes once, skipped does not; refill adds auditable movement; run-out forecast uses active fixed schedules; insufficient stock does not block truthful taken log; low-stock alert deduplicated. |
| CC-12 | Saif | Vitals/trend alerts | Validate units/ranges and bp pair; per-patient thresholds; deterministic documented trend rule with sufficient readings; threshold/trend alert once per source; invalid/missing readings do not become zero. |
| CC-13 | Tanjila | Symptom diary | Timestamped severity and history; configurable temporal association to new medicine/revision; flag as possible association, not diagnosis; unauthorized entries denied. |
| CC-14 | Saif | Appointment workflow | Schedule/remind, pre-visit checklist, complete/cancel, post-visit prescription prompt; cancelled visits do not send reminders; timezone displays correct. |
| CC-15 | Saif | Doctor summary/share | PDF combines authorized medicines/adherence/vitals/symptoms and period; expiring revocable read-only share; audit every access; revoked/expired token fails without exposing data. |
| CC-16 | Sandip | SOS/health card | One action records SOS and minimal health snapshot; optional consented location; critical alert bypasses quiet hours; unacknowledged event reaches configured email contact; no invented emergency-dispatch capability. |
| CC-17 | Tasin | Daily check-in | One response per patient-local date; missed grace triggers reminder then caregiver alert; repeated ticks/responses idempotent; cross-midnight timezone tests. |
| CC-18 | Sandip | Unified alerts | Feed prioritizes severity/time; scoped recipients only; read/acknowledge/resolve behavior; quiet hours defer noncritical email; ack stops escalation. |
| CC-19 | Sandip | Family tasks | Create/claim/complete/cancel with due dates; concurrent claim has one winner; assignee must retain circle access; revoke does not leak task data. |
| CC-20 | Sandip | Privacy controls | Sensitive access/change audit excludes raw data; authorized export with private expiry; explicit erasure revokes shares and removes associated files/data; unauthorized request denied and completion verified. |

## Required integration scenarios

1. Patient A and Patient B isolation across every list/detail/write/download route.
2. Confirm prescription -> future doses -> taken -> stock and analytics agree.
3. Revise/stop prescription -> pending future events cancelled; history unchanged.
4. Missed dose -> one alert -> staged delivery -> acknowledgement cancels remaining work.
5. Worker restart/retry and concurrent request tests prove durable effects are not duplicated.
6. Revoked circle membership/share link fails immediately, including pending delivery.
7. Summary reflects the same period/denominator as dashboard and contains only scoped data.
