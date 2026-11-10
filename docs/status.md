# Current implementation status

Whole-team Sprint 1 plus Sandip and Tanjila Sprint 2, 10 November 2026. See [validation](../VALIDATION.md) for local checks. This prepared folder has not been pushed to GitHub.

| Feature | Status |
|---|---|
| Sandip CC-01 | Care circles, consent, invitations, access changes and revocation; supporting authentication |
| Tanjila CC-03 | Medicine reference import, search, filters and generic alternatives |
| Tanjila CC-04 | Interaction/duplicate/reported-allergy warning review and immutable initial medicine confirmation |
| Tasin CC-06 | Transactional dose generation, UTC/local-time handling, rolling horizon refresh, permitted upcoming-dose view |
| Saif CC-12 | Vitals logging, thresholds and deterministic trend alerts |
| Sandip CC-18 | Scoped alert feed, read/acknowledge/resolve, pending-delivery cancellation, personal quiet-hour preferences and delivery gate |
| Tanjila CC-02 | Printed-English image recognition, editable persisted drafts and reviewed catalogue suggestions; explicit manual dose entry |
| Tanjila CC-05 | Immutable revision/stop history, atomic future-dose regeneration and authorized in-app change alerts |
| Schema | One additive chain ending at 0006_tanjila |
| Existing medicine records | Preserved; manual or daily refresh generates future doses without replaying elapsed times |
| Remaining 12 features | Later increments; reminders, adherence actions and the other unimplemented features remain later work |

Daily extension requires an operator to schedule `python -m app.refresh_schedules`; the UI also supports manual refresh. No reminder delivery or automatic scheduler installation is included. Medicine fixtures are fictional teaching data. Course records, SRS and individual contribution confirmation remain the team's responsibility.

See [Sandip Sprint 2](sandip-sprint-2.md). Quiet hours defer future noncritical email delivery, but this increment does not implement SMTP or escalation workers.

See [Tanjila Sprint 2](tanjila-sprint-2.md). Handwriting, Bengali OCR, clinical accuracy and email delivery are not claimed.
