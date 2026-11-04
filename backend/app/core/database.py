from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings


@lru_cache
def engine():
    return create_engine(settings()['database'], pool_pre_ping=True, isolation_level='READ COMMITTED')


def get_db():
    # Transaction completion happens before the route returns, not in this dependency.
    with Session(engine(), expire_on_commit=False) as session:
        yield session
