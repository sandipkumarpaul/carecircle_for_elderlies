# Tanjila Sprint 2 — CC-02 prescription OCR and CC-05 revisions/history

This increment extends whole-team Sprint 1 and Sandip's CC-18 alert centre. It preserves all prior features and introduces migration 0006_tanjila after 0005_sandip. Login/logout are still supporting functionality, not counted features.

## CC-02: printed prescription OCR

The patient or a caregiver with Manage medicines uploads a JPEG/PNG. The backend verifies access before receiving/processing the image and again after OCR, so access revoked during processing cannot save a result. Limits are 5 MB, 12 megapixels, a 32-pixel minimum dimension, two concurrent recognitions per API process and a 25-second recognition timeout. Invalid image content is rejected even if its filename or content type claims otherwise.

Pillow validates/decodes the image, applies EXIF orientation and re-encodes it to a temporary PNG. Local Tesseract with English pretrained recognition produces text and word confidence. The application uses catalogue name matching to suggest possible medicines. It does not infer quantities, frequencies, start/end dates, or clinical substitutions. The user corrects and saves the text, chooses an exact medicine/strength/form, enters dose instructions, checks warnings and explicitly confirms. No OCR result automatically changes prescriptions or doses.

The database retains original OCR text, reviewed text, confidence, author, timestamps and a review revision number. Uploaded images and temporary recognition files are discarded. OCR edits reject stale revision numbers. A warning review linked to OCR becomes stale if the OCR review changes. Once referenced by a confirmed prescription version, the reviewed draft cannot be edited; upload another image for a new review. Raw prescription text is not included in audit records or error responses.

Printed English is the supported demonstration scope. Handwriting, Bengali recognition, PDF documents and clinical extraction accuracy are not claimed. Confidence is recognition-engine confidence, not medicine correctness. Blank/low-confidence recognition allows manual transcription; unavailable/timed-out OCR presents manual-entry guidance. Catalogue matching uses deterministic name similarity; the recognition model is pretrained Tesseract, not a model trained by this team.

## OCR installation and sample

Install Python requirements as usual (Pillow is pinned in requirements.lock.txt). Install Tesseract 5 separately with English language data. Windows installers are linked from the [official Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation) through [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). Set `TESSERACT_CMD` in backend/.env to the installed executable, for example `C:/Program Files/Tesseract-OCR/tesseract.exe`, or leave `tesseract` if it is on PATH. Verify `tesseract --version` and `tesseract --list-langs`; `eng` must be present. Linux: install your distribution's `tesseract-ocr` and `tesseract-ocr-eng` packages. GitHub Actions installs them before tests.

No binary or local installation path is bundled in this repository. Local verification used Tesseract 5.5.3.20260724 and Pillow 13.0.0. `backend/data/prescription-demo.png` is an original fictional printed sample referencing the existing Demo Alpha medicine. It contains no real patient information and is not a medical prescription for use in care.

## CC-05: revisions and stopping

From Prescription version history, Manage medicines users can revise the entire item list of the current version. They enter a reason, change/add/remove items and run the existing warning review. The warning check excludes the version being replaced, but still checks all other active prescription roots, within-draft duplicates, reported allergies and curated interactions. Unacknowledged warnings block confirmation.

Confirmation takes effect immediately at the server's current time. It creates a new immutable version under the same prescription root, closes the old effective interval, and regenerates doses in the same transaction. Old medicine item contents remain unchanged. Only old pending dose events at/after the effective instant are cancelled; earlier events and taken/skipped/missed history remain. New items generate future doses under the existing horizon/DST rules. A failed regeneration or alert creation rolls back the complete change.

Stop is an explicit action requiring a reason and expected current version. It creates a stopped version with no items, closes the old interval and cancels only future pending doses. Concurrent/stale edits cannot overwrite a newer version. Retrying the same confirmed warning review returns the same version; retrying an identical stop by the same actor returns the existing stop version. A stopped root cannot be revised through the current-version action; a later prescription is entered as a new root.

Successful revisions and stops raise one `prescription_changed` alert per new version. The shared service selects currently authorized recipients with alerts and medicine read access. The alert appears in CC-18 after Refresh alerts. No email delivery is claimed. Read-only caregivers can view history but cannot revise, stop or upload/edit OCR.

## MVC and APIs

- Models: OcrDraft and added version/review provenance fields in models/medicines.py; additive migration 0006_tanjila. Prior versions are read-only except their effective-interval closure metadata.
- Controllers: controllers/ocr.py and controllers/medicines.py enforce sessions, CSRF, medicine scopes, patient locks, validated input and transaction boundaries.
- Services: services/ocr.py runs image recognition and catalogue matching; services/medicines.py validates current versions, evaluates warnings, confirms/stops and notifies; existing schedules/alerts services are reused.
- Views: PrescriptionOCR.tsx, PrescriptionHistory.tsx and the existing MedicineView.tsx draft editor.

All paths below begin `/api/v1/patients/{patient_id}`:

| Method/path | Behaviour |
|---|---|
| POST /ocr | Raw image/png or image/jpeg request body; session CSRF required; returns draft and suggestions |
| GET /ocr | Paginated draft summaries, default 10, maximum 50 |
| GET /ocr/{id} | Authorized draft text, status, review revision and suggestions |
| PUT /ocr/{id} | reviewed_text and expected_revision; stale/finalized edits rejected |
| POST /interaction-check | Existing items plus optional replaces_version_id, change_reason and ocr_draft_id |
| POST /prescriptions/confirm | Existing check_id and acknowledgement IDs; same route handles new roots and reviewed revisions |
| GET /prescription-history | Version/item history, offset/limit; default 20, maximum 100 |
| POST /prescriptions/{root_id}/stop | expected_version_id and reason; immediate stop with history |

Revision/stop lock order remains reference revision first, then patient. OCR processing releases database locks while the engine runs and reacquires/rechecks permission before persistence. The in-process OCR slot limit is per worker; production deployment still needs normal resource/request-rate limits.

## Faculty walkthrough

1. Run migrations, configure Tesseract and import medicines-demo.csv using the existing reference administrator workflow.
2. Select a patient. Upload prescription-demo.png under Read a printed prescription image and click Extract prescription text.
3. Inspect the original text; correct Reviewed prescription text and Save reviewed text. Choose Use suggestion: Demo Alpha. Enter tomorrow's start date, quantity 1 and 08:00, 20:00; add, check and confirm.
4. Verify upcoming doses and Version 1 in history. Reload to demonstrate persistence.
5. Choose Revise this prescription. Enter a reason, Edit item 1, change quantity to 2 and Add to proposed list. Check and confirm. Version 2 becomes current; Version 1 remains visible with quantity 1; future doses show quantity 2. Refresh alerts to see Prescription changed.
6. Stop this prescription, enter the recorded clinician reason and Confirm stop. Version 3 shows Stopped; future pending doses disappear while earlier versions remain.
7. Try a blank image, invalid file or read-only caregiver to demonstrate fallback and permission boundaries. Changes in this demonstration record clinician instructions; they are not recommendations to change treatment.
