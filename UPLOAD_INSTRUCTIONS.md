# Upload whole-team Sprint 1 plus Sandip and Tanjila Sprint 2

Prepared from the verified Sandip Sprint 2 folder matching GitHub main commit `20b80a3`. This package adds Tanjila CC-02 prescription OCR and CC-05 revisions/history while retaining all previous team features.

1. In GitHub Desktop, sign in as Tanjila and set this repository's Git name/email to her account's author details.
2. Select the existing carecircle_for_elderlies repository, select main, Fetch origin and Pull origin. If teammates added work after 20b80a3, merge that work before copying this snapshot.
3. Copy the **contents** of whole_team_S1_SandipANDTanjila_S2 into the clone's root, replacing matching files. Preserve the clone's .git directory. Do not create an extra wrapper folder in GitHub.
4. Include all dotfiles, especially the updated .github/workflows/checks.yml (which installs the OCR engine for tests) and backend/.env.example. Local .env files, databases, installed runtimes, dependencies and generated outputs are excluded from this package.
5. Review Changes and commit with `Add Tanjila Sprint 2 prescription OCR and version history`, then Push origin.
6. Wait for GitHub Actions to pass before announcing the update as verified on GitHub. Local results are in VALIDATION.md.

The five misplaced root files from the earlier Tasin upload were already removed in the verified GitHub baseline; no repeat deletion is required. Their correct backend paths are retained here.

For a local run, install requirements and Tesseract 5 with English data, configure backend/.env, and run `alembic upgrade head` through 0006_tanjila. See docs/tanjila-sprint-2.md for setup and the demonstration. The old whole_team_S1_Sandip_S2 and Whole_Team_Sprint1 folders remain unchanged. Nothing has been uploaded automatically.
