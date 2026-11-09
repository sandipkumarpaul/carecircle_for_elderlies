"""Run daily with python -m app.refresh_schedules to extend dose horizons.

Configure the normal DATABASE_URL. This is a one-shot operator command, not a
reminder worker. Per-patient locks serialize refresh with confirmation/revocation.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.identity import utcnow
from app.models.medicines import PrescriptionVersion
from app.services.circle import locked_patient
from app.services.schedules import ScheduleService


def main():
    with Session(engine()) as db:
        ids = list(db.scalars(select(PrescriptionVersion.patient_id).distinct()
                             .where(PrescriptionVersion.status == 'confirmed')))
    for patient_id in ids:
        with Session(engine()) as db, db.begin():
            locked_patient(db, patient_id)
            now = utcnow()
            versions = db.scalars(select(PrescriptionVersion).where(
                PrescriptionVersion.patient_id == patient_id, PrescriptionVersion.status == 'confirmed',
                (PrescriptionVersion.effective_until.is_(None)) | (PrescriptionVersion.effective_until > now)))
            for version in versions:
                ScheduleService().extend_version(db, version, now)
    print(f'Schedule refresh completed for {len(ids)} patient profiles.')


if __name__ == '__main__':
    main()
