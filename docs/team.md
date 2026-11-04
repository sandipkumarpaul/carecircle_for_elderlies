# Team responsibilities and implementation handoff

These assignments are the team's supplied roadmap. All five features per person remain individually owned; shared tasks are additional.

| Member | Features | Shared responsibility | Start with |
|---|---|---|---|
| Sandip Kumar Paul | CC-01, CC-16, CC-18, CC-19, CC-20 | Authentication, patient authorization, alert creation | Review the completed CC-01 baseline; next assessed feature is CC-18 |
| Tanjila Afsari Rubina | CC-02, CC-03, CC-04, CC-05, CC-13 | Database setup and migration coordination | Extend migration 0001_sandip; Sprint 1 CC-03 medicine import/search and CC-04 interaction/duplicate/allergy warnings |
| Moinuddin Tasin | CC-06, CC-07, CC-08, CC-11, CC-17 | Separate scheduler worker, notification transport | Schedule generation from confirmed prescription versions, durable dose events and adherence log |
| Md Shahriar Saif | CC-09, CC-10, CC-12, CC-14, CC-15 | Shared frontend shell, API client, integration test coordination | CC-12 vitals with permission checks; risk experiment using explicitly synthetic data; summary last |

## Sandip — implementation notes

Auth, CC-01, `PermissionService.require` and `AlertService.raise_alert` are implemented. Review docs/sandip-sprint-1.md and the current identity/membership/alerts/audit models before extending them. Tasin sends email; your service stores alerts and recipient rows, not SMTP. Build tests for revoked membership and cross-patient requests. Own auth/login UI, circle UI, alert feed, SOS, tasks, privacy screens. Review topics: JWT verification, consent enforcement and audit behavior.

## Tanjila — implementation notes

Identity, sessions, circles and alert persistence now exist in migration 0001_sandip. Extend this chain and reuse User/Patient/permissions; do not create duplicates. Start a small curated reference dataset with explicit provenance/license. Sprint 1 is CC-03 CSV validation/deduplication/search and CC-04 interaction/duplicate/allergy warnings, with minimum prescription/active-medication structures needed to demonstrate that workflow. Later preserve immutable confirmed prescription versions and call Tasin's regeneration interface transactionally. OCR is Sprint 2 and requires editable suggestions and human confirmation. Review topics: medicine identity, import validation and warning-rule provenance.

## Tasin — implementation notes

Implement `ScheduleService.regenerate` and `AdherenceService.record`. Past dose events/history are immutable. Use unique event keys, database locking, and one transaction for confirmation/stock effects. Implement the separate worker only after persistence exists. Reconcile due work after restart; use injected time in tests. Consume Sandip's alert service rather than building a separate alert table. Own dose UI, reminders/escalation, stock, and check-ins. Review topics: timezone conversion, retries, deduplication and concurrent confirmation.

## Saif — implementation notes

Extend the existing UI shell/API client without rewriting everyone's views. Start vitals persistence, per-patient thresholds, and alerts via Sandip's interface. Consume Tasin's canonical dose/adherence records for analytics and risk; do not calculate a different denominator. Risk uses past-only features, a time-based split, recorded seed and evaluation; label synthetic experiments. Do not fabricate probabilities if no model is available. Implement appointment workflow, weekly digest, then CC-15 after all sources integrate. Review topics: thresholds versus predictions and summary authorization.

## Starting a contribution

Read README.md and docs/status.md, inspect the current implementation, then select your assigned feature and its acceptance criteria. Identify producer/consumer dependencies in docs/contracts.md before changing shared types. Follow CONTRIBUTING.md for branches, migration sequencing, testing and review. Existing Sandip Sprint 1 functionality must continue to work as new modules are added.
