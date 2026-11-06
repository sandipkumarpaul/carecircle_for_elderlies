"""Local operator command; never exposed as a registration or HTTP privilege."""
import argparse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models import User, AuditEvent


def main():
    parser = argparse.ArgumentParser(description='Grant or revoke reference-catalogue administration for an existing account.')
    parser.add_argument('email')
    parser.add_argument('--revoke', action='store_true')
    args = parser.parse_args()
    with Session(engine()) as db, db.begin():
        user = db.scalar(select(User).where(User.email_normalized == args.email.strip().casefold()).with_for_update())
        if not user or user.disabled_at:
            raise SystemExit('Active registered account not found')
        user.is_admin = not args.revoke
        db.add(AuditEvent(action='reference_admin_revoked' if args.revoke else 'reference_admin_granted',
                          resource_type='users', resource_id=user.id))
    print('Reference administrator access updated. Patient access is unchanged.')


if __name__ == '__main__':
    main()
