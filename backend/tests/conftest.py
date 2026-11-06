import os
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.main import app
from app.models import Base
from app.models.medicines import ReferenceRevision


@pytest.fixture(scope='session')
def mysql_database():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env.test')
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL for real MySQL integration tests')
    parsed = make_url(url)
    if parsed.drivername != 'mysql+pymysql' or not parsed.database.endswith('_test'):
        raise RuntimeError('Refusing tests: dedicated MySQL database name must end with _test')
    old = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = url
    os.environ.setdefault('JWT_SECRET', 'test-only-not-for-deployment-' + uuid4().hex)
    os.environ['APP_ORIGIN'] = 'http://localhost:5173'
    settings.cache_clear(); engine.cache_clear()
    with engine().connect() as connection:
        version = connection.scalar(text('SELECT VERSION()'))
        assert version.startswith('8.4.'), f'Requires MySQL 8.4, got {version}'
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    command.upgrade(config, 'head')
    yield engine()
    engine().dispose(); engine.cache_clear(); settings.cache_clear()
    if old is None:
        os.environ.pop('DATABASE_URL', None)
    else:
        os.environ['DATABASE_URL'] = old


@pytest.fixture
def db_engine(mysql_database):
    # Delete only known application tables in the explicitly guarded test database.
    with Session(mysql_database) as session, session.begin():
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        session.add(ReferenceRevision(id=1, revision=0))
    return mysql_database


@pytest.fixture
def accounts(db_engine):
    with ExitStack() as stack:
        def create(name):
            client = stack.enter_context(TestClient(app))
            email = f'{name}-{uuid4().hex[:8]}@example.com'
            token = client.get('/api/v1/auth/csrf').json()['csrf_token']
            client.headers.update({'Origin': 'http://localhost:5173', 'X-CSRF-Token': token})
            result = client.post('/api/v1/auth/register', json=dict(email=email, display_name=name, password='Correct-demo-password-123'))
            assert result.status_code == 201, result.text
            body = result.json()
            client.headers['X-CSRF-Token'] = body['csrf_token']
            return client, body['user']
        yield create


@pytest.fixture
def owner(accounts):
    client, user = accounts('Patient')
    result = client.post('/api/v1/patients', json=dict(display_name='Synthetic Patient', timezone='Asia/Dhaka',
                         kind='self', consent=True, consent_basis='I consent to this synthetic test profile.'))
    assert result.status_code == 201, result.text
    return client, user, result.json()
