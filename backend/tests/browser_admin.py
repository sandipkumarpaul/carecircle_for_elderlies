"""Test-only privilege setup, guarded to the explicitly configured test database."""
import sys
from tests import run_browser_server  # validates test URL and isolates DATABASE_URL
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models import User

with Session(engine()) as db, db.begin():
    user = db.scalar(select(User).where(User.email_normalized == sys.argv[1]))
    if not user:
        raise SystemExit('Synthetic browser account missing')
    user.is_admin = True
