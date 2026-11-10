import csv
import hashlib
import io
import json
from datetime import date, timedelta
from difflib import SequenceMatcher
from itertools import combinations
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from app.models import AuditEvent
from app.models.medicines import (Medicine, InteractionRule, Prescription, PrescriptionVersion,
                                  PrescriptionItem, WarningCheck, ReferenceRevision, OcrDraft)
from app.schemas.medicines import MedicineInput, normalized
from app.schemas.contracts import PrescriptionItemInput, RegenerateScheduleCommand
from app.services.schedules import ScheduleService
from app.services.alerts import AlertService
from app.schemas.contracts import RaiseAlertCommand


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def reference_lock(db):
    return db.scalar(select(ReferenceRevision).where(ReferenceRevision.id == 1).with_for_update()
                     .execution_options(populate_existing=True))


def medicine_view(row):
    return dict(id=row.id, **{field: getattr(row, field) for field in MedicineInput.model_fields})


def import_csv(db, text, actor):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')), strict=True)
    fields = set(MedicineInput.model_fields)
    if reader.fieldnames is None or len(reader.fieldnames) != len(fields) or set(reader.fieldnames) != fields:
        return dict(imported=0, duplicates=0, errors=[dict(row=1, message='CSV header must contain exactly: ' + ', '.join(MedicineInput.model_fields))])
    rows, errors = {}, []
    duplicates = 0
    try:
        for number, values in enumerate(reader, 2):
            if number > 501:
                errors.append(dict(row=number, message='Maximum 500 medicine rows')); break
            try:
                item = MedicineInput.model_validate(values)
                data = item.model_dump()
                key = digest([normalized(data[k]) for k in ('generic_name', 'brand_name', 'strength', 'form')])
                if key in rows:
                    duplicates += 1
                rows[key] = data
            except ValidationError as exc:
                errors.append(dict(row=number, message='Invalid fields: ' + ', '.join(str(e['loc'][0]) for e in exc.errors())))
    except csv.Error:
        errors.append(dict(row=reader.line_num, message='Malformed CSV quoting'))
    if not rows and not errors:
        errors.append(dict(row=2, message='CSV has no medicine rows'))
    if errors:
        return dict(imported=0, duplicates=0, errors=errors)
    revision = reference_lock(db)
    known = set(db.scalars(select(Medicine.normalized_key).where(Medicine.normalized_key.in_(rows))))
    for key, values in rows.items():
        if key not in known:
            db.add(Medicine(normalized_key=key, **values))
    imported = len(rows) - len(known)
    if imported:
        revision.revision += 1
        db.add(AuditEvent(actor_user_id=actor.id, action='medicine_import', resource_type='users', resource_id=actor.id))
    db.flush()
    return dict(imported=imported, duplicates=duplicates + len(known), errors=[])


def search(db, query, strength, form, offset, limit, generic=''):
    stmt = select(Medicine)
    if strength:
        stmt = stmt.where(Medicine.strength == strength.replace(' ', ''))
    if form:
        stmt = stmt.where(Medicine.form == form)
    # Bounded teaching catalogue: ranking scans reference rows, never patient records.
    rows = list(db.scalars(stmt.order_by(Medicine.brand_name, Medicine.id)))
    q = normalized(query)
    ranked = []
    for row in rows:
        if generic and normalized(row.generic_name) != normalized(generic):
            continue
        names = [normalized(row.brand_name), normalized(row.generic_name)]
        score = max((1.0 if q in name else SequenceMatcher(None, q, name).ratio()) for name in names) if q else 1
        if score >= .6:
            ranked.append((score, row))
    ranked.sort(key=lambda pair: (-pair[0], normalized(pair[1].brand_name), pair[1].id))
    return dict(items=[medicine_view(row) for _, row in ranked[offset:offset+limit]], total=len(ranked), offset=offset, limit=limit)


def active_items(db, patient_id, now):
    rows = db.execute(select(PrescriptionItem, Medicine, PrescriptionVersion)
        .join(Medicine, Medicine.id == PrescriptionItem.medicine_id)
        .join(PrescriptionVersion, PrescriptionVersion.id == PrescriptionItem.prescription_version_id)
        .where(PrescriptionItem.patient_id == patient_id, PrescriptionVersion.patient_id == patient_id,
               PrescriptionVersion.status == 'confirmed', PrescriptionVersion.effective_from <= now)).all()
    # Include future-starting prescriptions when checking overlap with proposed dates.
    return [(item, med, version) for item, med, version in rows
            if (version.effective_until is None or version.effective_until > now)
            and (item.end_date is None or item.end_date >= now.astimezone(ZoneInfo(item.timezone)).date())]


def evaluate(db, patient, items, now, revision, replaces_version_id=None):
    medicines = {m.id: m for m in db.scalars(select(Medicine).where(Medicine.id.in_([str(i.medicine_id) for i in items])))}
    if len(medicines) != len(set(str(i.medicine_id) for i in items)):
        raise HTTPException(422, 'One or more medicines do not exist')
    units = {'tablet': 'tablet', 'capsule': 'capsule', 'liquid': 'ml', 'drops': 'drop', 'inhaler': 'puff', 'injection': 'unit', 'cream': 'unit'}
    for item in items:
        if units[medicines[str(item.medicine_id)].form] != item.unit:
            raise HTTPException(422, 'Dose unit does not match medicine form')
        if item.end_date and item.end_date < now.astimezone(ZoneInfo(item.timezone)).date():
            raise HTTPException(422, 'Cannot add an already-ended medicine record')
    existing = [(i, m, v) for i, m, v in active_items(db, patient.id, now) if v.id != replaces_version_id]
    proposed = [(f'proposed:{n}', medicines[str(i.medicine_id)], i.start_date, i.end_date, True) for n, i in enumerate(items)]
    current = [(i.id, med, i.start_date, i.end_date, False) for i, med, _ in existing]
    rules = list(db.scalars(select(InteractionRule).order_by(InteractionRule.id)))
    # Rules apply to the referenced generic pair across brands/strengths, not just one brand.
    all_meds = {m.id: m for m in db.scalars(select(Medicine))}
    warnings = []
    def warn(key, kind, severity, message, source):
        warnings.append(dict(id=digest(key), kind=kind, severity=severity, message=message, source=source))
    for key, med, _, _, _ in proposed:
        if normalized(med.generic_name) in patient.allergies:
            warn(['allergy', key, med.id], 'allergy', 'critical', f'{med.brand_name}: matches a recorded generic allergy ({med.generic_name}).', 'Patient/caregiver-reported generic allergy; exact normalized match')
    for a, b in combinations(proposed + current, 2):
        if not (a[4] or b[4]) or max(a[2], b[2]) > min(a[3] or date.max, b[3] or date.max):
            continue
        ga, gb = normalized(a[1].generic_name), normalized(b[1].generic_name)
        if ga == gb:
            warn(['duplicate', a[0], b[0]], 'duplicate', 'warning', f'{a[1].brand_name} and {b[1].brand_name} contain the same generic ({a[1].generic_name}).', 'CareCircle exact generic-name duplicate rule')
        for rule in rules:
            pair = {normalized(all_meds[rule.medicine_a_id].generic_name), normalized(all_meds[rule.medicine_b_id].generic_name)}
            if {ga, gb} == pair:
                warn(['interaction', a[0], b[0], rule.id], 'interaction', rule.severity,
                     f'{a[1].brand_name} + {b[1].brand_name}: {rule.explanation}', rule.source)
    warnings.sort(key=lambda w: w['id'])
    state = digest(dict(reference=revision.revision, allergies=patient.allergies,
                        active=sorted(i.id for i, _, _ in existing), warnings=warnings))
    return warnings, state


def current_version(db, patient, version_id):
    version = db.get(PrescriptionVersion, str(version_id))
    if not version or version.patient_id != patient.id:
        raise HTTPException(404, 'Prescription version not found')
    latest = db.scalar(select(PrescriptionVersion).where(PrescriptionVersion.prescription_id == version.prescription_id)
        .order_by(PrescriptionVersion.version_number.desc()).limit(1))
    if latest.id != version.id or version.status != 'confirmed' or version.effective_until is not None:
        raise HTTPException(409, 'Prescription changed or stopped; reload its history')
    return version


def ocr_context(db, patient, draft_id):
    if draft_id is None:
        return None
    draft = db.get(OcrDraft, str(draft_id))
    if not draft or draft.patient_id != patient.id:
        raise HTTPException(404, 'OCR draft not found')
    if draft.reviewed_at is None:
        raise HTTPException(409, 'Review and save the extracted text first')
    return [draft.id, draft.edit_revision]


def check(db, patient, actor, data, now, revision):
    previous = current_version(db, patient, data.replaces_version_id) if data.replaces_version_id else None
    source = ocr_context(db, patient, data.ocr_draft_id)
    warnings, state = evaluate(db, patient, data.items, now, revision, previous.id if previous else None)
    state = digest([state, source])
    record = WarningCheck(patient_id=patient.id, actor_user_id=actor.id,
        proposed_items=[i.model_dump(mode='json') for i in data.items], warnings=warnings,
        state_hash=state, expires_at=now + timedelta(minutes=15),
        replaces_version_id=previous.id if previous else None, change_reason=data.change_reason,
        ocr_draft_id=str(data.ocr_draft_id) if data.ocr_draft_id else None)
    db.add(record); db.flush()
    return dict(check_id=record.id, warnings=warnings, expires_at=record.expires_at,
                coverage='Limited curated rules and exact generic allergies only. No warnings does not establish safety.')


def confirm(db, patient, actor, data, now, revision):
    record = db.get(WarningCheck, str(data.check_id))
    if not record or record.patient_id != patient.id or record.actor_user_id != actor.id:
        raise HTTPException(404, 'Warning review not found')
    if set(data.acknowledged_warning_ids) != {w['id'] for w in record.warnings}:
        raise HTTPException(409, 'Acknowledge every warning before saving')
    if record.confirmed_version_id:
        version = db.get(PrescriptionVersion, record.confirmed_version_id)
        return dict(version_id=version.id, schedule_status=version.schedule_status)
    if record.expires_at <= now:
        raise HTTPException(409, 'Review expired; run the warning check again')
    items = [PrescriptionItemInput.model_validate(i) for i in record.proposed_items]
    previous = current_version(db, patient, record.replaces_version_id) if record.replaces_version_id else None
    source = ocr_context(db, patient, record.ocr_draft_id)
    _, state = evaluate(db, patient, items, now, revision, previous.id if previous else None)
    state = digest([state, source])
    if state != record.state_hash:
        raise HTTPException(409, 'Medicines, allergies or reference data changed; check again')
    root = db.get(Prescription, previous.prescription_id) if previous else Prescription(patient_id=patient.id, created_by=actor.id)
    if previous is None:
        db.add(root); db.flush()
    else:
        previous.effective_until = now
    version = PrescriptionVersion(prescription_id=root.id, patient_id=patient.id, version_number=previous.version_number + 1 if previous else 1,
        status='confirmed', effective_from=now, confirmed_by=actor.id, confirmed_at=now,
        previous_version_id=previous.id if previous else None, change_reason=record.change_reason,
        ocr_draft_id=record.ocr_draft_id)
    db.add(version); db.flush()
    for item in items:
        values = item.model_dump(); values['medicine_id'] = str(item.medicine_id)
        db.add(PrescriptionItem(patient_id=patient.id, prescription_version_id=version.id, **values))
    record.acknowledged_at = now if record.warnings else None
    record.confirmed_version_id = version.id
    db.add(AuditEvent(patient_id=patient.id, actor_user_id=actor.id, action='medicine_record_confirmed',
                      resource_type='prescription_versions', resource_id=version.id))
    db.flush()
    ScheduleService().regenerate(db, RegenerateScheduleCommand(
        patient_id=patient.id, prescription_id=root.id, new_version_id=version.id,
        previous_version_id=previous.id if previous else None,
        effective_from=now), now)
    if previous:
        notify_change(db, patient, version, now)
    return dict(version_id=version.id, schedule_status=version.schedule_status)


def notify_change(db, patient, version, now):
    AlertService().raise_alert(db, RaiseAlertCommand(patient_id=patient.id, type='prescription_changed',
        severity='info', source_type='prescription_version', source_id=version.id,
        dedupe_key=f'prescription_changed:{version.id}'), now)


def stop(db, patient, actor, root_id, data, now):
    root = db.get(Prescription, str(root_id))
    if not root or root.patient_id != patient.id:
        raise HTTPException(404, 'Prescription not found')
    latest = db.scalar(select(PrescriptionVersion).where(PrescriptionVersion.prescription_id == root.id)
        .order_by(PrescriptionVersion.version_number.desc()).limit(1))
    if latest and latest.status == 'stopped' and latest.previous_version_id == str(data.expected_version_id):
        if latest.confirmed_by != actor.id or latest.change_reason != data.reason:
            raise HTTPException(409, 'Prescription already stopped; reload history')
        return dict(version_id=latest.id, status='stopped')
    previous = current_version(db, patient, data.expected_version_id)
    if previous.prescription_id != root.id:
        raise HTTPException(404, 'Prescription version not found')
    previous.effective_until = now
    stopped = PrescriptionVersion(prescription_id=root.id, patient_id=patient.id, version_number=previous.version_number + 1,
        previous_version_id=previous.id, change_reason=data.reason, status='stopped', schedule_status='stopped',
        effective_from=now, confirmed_by=actor.id, confirmed_at=now)
    db.add(stopped); db.flush()
    ScheduleService().regenerate(db, RegenerateScheduleCommand(patient_id=patient.id, prescription_id=root.id,
        previous_version_id=previous.id, effective_from=now), now)
    notify_change(db, patient, stopped, now)
    db.add(AuditEvent(patient_id=patient.id, actor_user_id=actor.id, action='prescription_stopped',
                      resource_type='prescription_versions', resource_id=stopped.id))
    db.flush()
    return dict(version_id=stopped.id, status='stopped')
