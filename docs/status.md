# Current status

Implementation baseline: 4 November 2026. Documentation reorganized: 5 November 2026. Student review and viva preparation remain the team's responsibility. Hosted CI and review status must be recorded when they occur.

| Area | Status |
|---|---|
| Ownership, architecture, shared schema and interface decisions | Drafted as implementation defaults |
| Authentication and care-circle React UI | Implemented; see VALIDATION.md for actual checks |
| Shared Pydantic schemas and service Protocols | Implemented; schedule/adherence remain interfaces only |
| MySQL models / Alembic migrations | Identity, consent, circle, audit and alert foundation implemented in 0001_sandip |
| Auth / permission / alert services | Implemented; alerts are internal persistence only, no SMTP/feed |
| CC-01 | Implemented locally; 36 backend tests and 2 browser checks pass; student review/viva understanding pending |
| CC-02–CC-20 | Not implemented; original ownership unchanged |
| Runtime OpenAPI | Implemented auth/patient/circle endpoints, not planned clinical routes |
| Faculty FastAPI exception | Reported by team in prior chat; retain actual evidence privately |
| SRS and course tracker | External SRS link blank and tracker feature labels still placeholders at review time; unchanged |

Owners update this with evidence as work lands. Existing acceptance criteria do not equal passing tests. Use not-started / in-progress / blocked / complete, with PR/test evidence for completion.

Latest course timetable requires five features team-wide by 8 November for Sprint 1. Sandip owns CC-01; Tanjila CC-03/04; Tasin CC-06; Saif CC-12. Authentication does not count toward the five.
