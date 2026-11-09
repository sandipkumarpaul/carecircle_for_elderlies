# Upload whole-team Sprint 1 plus Sandip Sprint 2

This folder is based on GitHub main commit `6527df4` and includes all four members' Sprint 1 work plus dose-engine integration corrections and Sandip CC-18 alert centre. Upload its **contents** into the repository root; do not create an extra whole_team_S1_Sandip_S2 folder inside GitHub.

1. Check that main has no newer teammate commits before uploading. If it has changed since `6527df4`, merge those changes first rather than overwriting them with this snapshot.
2. Delete these five misplaced files from the **GitHub repository root only**: `0004_tasin_dose_events.py`, `__init__.py`, `doses.py`, `schedules.py`, `test_schedules.py`. Their corrected copies are now under backend. Uploading a folder through GitHub does not remove old files automatically.
3. Upload the contents of this folder, preserving backend, frontend, docs, scripts and .github. Keep the existing .github workflow and pull-request template; they have not changed. Include root dotfiles if your upload method supports them. Never upload local .env files, dependencies or databases.
4. Suggested commit message: `Add Sandip Sprint 2 alert centre on whole-team Sprint 1`.
5. Check GitHub Actions after committing. Local results are recorded in VALIDATION.md; hosted results are only established after that run.

For local setup follow README.md and apply `alembic upgrade head`. Existing medicine records remain intact; Refresh dose schedule generates their future events. See docs/tasin-sprint-1.md for the demonstration and daily refresh command.

Using Git or GitHub Desktop to stage both removals and additions allows the correction to be committed atomically. If using the web upload interface, complete all deletions and uploads before asking teammates to pull.

Apply migrations through 0005_sandip when running this version. Review docs/sandip-sprint-2.md and VALIDATION.md before the Sprint 2 demonstration. The original Whole_Team_Sprint1 folder is retained separately.
