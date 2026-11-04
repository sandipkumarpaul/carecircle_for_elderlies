# Course deadlines and feature plan

The user supplied the course timetable on 2026-11-04. It supersedes the earlier proposed one-week schedule. **Five substantive features per sprint across the whole team**, not per person. Authentication and setup are supporting work, not counted features. Sprint 0 setup/SRS/class-diagram deadline: 24 October 2026. Final demonstration: 30 December 2026.

| Sprint / deadline (2026) | Sandip | Tanjila | Tasin | Saif | Count |
|---|---|---|---|---|---|
| 1 — 8 November | CC-01 | CC-03, CC-04 | CC-06 | CC-12 | 5 |
| 2 — 25 November | CC-18 | CC-02, CC-05 | CC-07 | CC-14 | 5 |
| 3 — 9 December | CC-16 | CC-13 | CC-08, CC-11 | CC-10 | 5 |
| 4 — 28 December | CC-19, CC-20 | Integration and testing | CC-17 | CC-09, CC-15 | 5 |

Sprint 1 assignments reflect the latest conversation; later distributions are a proposed dependency-aware plan. Every member still owns exactly five assessed features overall. No row claims completion.

Sandip's Sprint 1 supporting work: authentication, identity, the shared permission service, and internal alert persistence. Identity/circle migration was implemented with this work because it is required for CC-01. Tanjila must extend the existing `0001_sandip` migration chain, not create a parallel initial schema. Her own Sprint 1 covers medicine import/search and interaction/duplicate/allergy warnings. OCR is deferred to Sprint 2; an experiment is not a completed CC-02.

Use a weekly record with planned goals, actual completed/partial/not-started items, real commits/PRs, commands and outcomes, blockers, and next actions. Do not pre-fill attainment. If scope slips, document it and coordinate instead of marking unfinished work done.
