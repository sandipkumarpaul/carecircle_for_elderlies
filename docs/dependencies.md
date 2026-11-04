# Package and data inventory

Exact installed versions: backend/requirements.lock.txt and frontend/package-lock.json. Inspect those files rather than manually copying version numbers into several documents.

| Package | Purpose | Upstream license family (verify installed release when redistributing) |
|---|---|---|
| FastAPI / Pydantic / Uvicorn | API / schema validation / local ASGI server | MIT / MIT / BSD |
| tzdata | IANA timezone data on Windows | Apache-2.0 |
| pytest / httpx | Tests / in-process HTTP test client | MIT / BSD |
| React / React DOM / MUI / Emotion | Views and UI styling | MIT |
| Vite / TypeScript / React Vite plugin / React typings | Development/build tooling | MIT / Apache-2.0 / MIT / MIT |

Added for Sandip Sprint 1: SQLAlchemy 2 (ORM, MIT), PyMySQL with RSA/cryptography support (MySQL driver, MIT; cryptography Apache/BSD), Alembic (migrations, MIT), PyJWT (JWT primitives, MIT), argon2-cffi (password hashing, MIT), python-dotenv (local config, BSD), email-validator (email syntax, Unlicense), and Playwright (browser tests, Apache-2.0). Exact versions are in dependency locks. These provide primitives; the circle and consent workflows are application code.

Deferred: APScheduler 3 (Tasin); pytesseract/Pillow and separately installed Tesseract 5 (Tanjila); scikit-learn/Recharts/ReportLab (Saif). Record exact versions/licenses when introduced. A local MySQL Community 8.4.13 Windows ZIP from the official MySQL CDN was used for tests; the binaries/data are outside this source folder and are not redistributed.

No medicine/interaction dataset is bundled. Do not invent licenses or citations. Choose a small curated legally usable set, record provenance and date, and label incomplete coverage. Synthetic adherence/vitals data must be labeled and generated reproducibly; no real patient data should be committed.
