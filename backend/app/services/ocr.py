"""Printed-English OCR using a local Tesseract process; never prescribes medicines."""
import csv
import io
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import warnings
from difflib import SequenceMatcher
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException
from sqlalchemy import select
from app.models.medicines import Medicine, PrescriptionVersion
from app.schemas.medicines import normalized
from app.services.medicines import medicine_view

MAX_UPLOAD = 5 * 1024 * 1024
MAX_PIXELS = 12_000_000
_slots = threading.BoundedSemaphore(2)


def extract(content: bytes):
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, 'OCR is busy; try again shortly or enter the prescription manually')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            try:
                with Image.open(io.BytesIO(content), formats=['JPEG', 'PNG']) as image:
                    if image.width * image.height > MAX_PIXELS or min(image.size) < 32:
                        raise HTTPException(422, 'Use a readable image between 32 pixels and 12 megapixels')
                    image.load()
                    clean = ImageOps.exif_transpose(image).convert('RGB')
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
                raise HTTPException(422, 'Invalid JPEG/PNG image; use manual entry or upload a clear image')
        with tempfile.TemporaryDirectory(prefix='carecircle-ocr-') as folder:
            path = Path(folder) / 'prescription.png'
            clean.save(path, format='PNG')
            clean.close()
            command = [os.environ.get('TESSERACT_CMD', 'tesseract'), str(path), 'stdout', '-l', 'eng', '--psm', '6', 'tsv']
            try:
                result = subprocess.run(command, capture_output=True, timeout=25, check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except FileNotFoundError:
                raise HTTPException(503, 'OCR engine is not installed; manual medicine entry remains available')
            except subprocess.TimeoutExpired:
                raise HTTPException(504, 'OCR timed out; try a clearer image or enter the prescription manually')
            if result.returncode:
                raise HTTPException(503, 'OCR could not process this image; try manual entry')
            lines, confidence = {}, []
            for word in csv.DictReader(io.StringIO(result.stdout.decode('utf-8', errors='replace')), delimiter='\t'):
                if word.get('level') != '5' or not (word.get('text') or '').strip():
                    continue
                key = tuple(word.get(k) for k in ('page_num','block_num','par_num','line_num'))
                lines.setdefault(key, []).append(word['text'].strip())
                try:
                    score = float(word['conf'])
                    if 0 <= score <= 100:
                        confidence.append(score)
                except (KeyError, ValueError):
                    pass
            text = '\n'.join(' '.join(words) for words in lines.values())[:20000]
            score = round(sum(confidence) / len(confidence), 2) if confidence else None
            return dict(text=text, confidence=score, status='no_text' if not text else 'low_confidence' if score is None or score < 65 else 'recognized')
    finally:
        _slots.release()


def suggestions(db, text):
    """Catalogue matches only; no inferred dose, frequency or substitution."""
    lines = [normalized(line) for line in text.splitlines() if line.strip()][:200]
    matches = []
    for med in db.scalars(select(Medicine).order_by(Medicine.brand_name, Medicine.id)):
        score = 0.0
        for name in (normalized(med.brand_name), normalized(med.generic_name)):
            for line in lines:
                words, size = line.split(), len(name.split())
                candidates = [' '.join(words[i:i+size]) for i in range(max(0, len(words)-size+1))]
                score = max([score] + [SequenceMatcher(None, name, value).ratio() for value in candidates])
        if score >= .72:
            matches.append(dict(medicine=medicine_view(med), match_score=round(score, 2)))
    return sorted(matches, key=lambda r: (-r['match_score'], r['medicine']['brand_name']))[:20]


def view(db, draft):
    locked = db.scalar(select(PrescriptionVersion.id).where(PrescriptionVersion.ocr_draft_id == draft.id).limit(1)) is not None
    return dict(id=draft.id, raw_text=draft.raw_text, reviewed_text=draft.reviewed_text,
        locked=locked,
        recognition_status=draft.recognition_status, confidence=str(draft.confidence) if draft.confidence is not None else None,
        reviewed_at=draft.reviewed_at, edit_revision=draft.edit_revision, created_at=draft.created_at,
        suggestions=suggestions(db, draft.reviewed_text if draft.reviewed_at else draft.raw_text))
