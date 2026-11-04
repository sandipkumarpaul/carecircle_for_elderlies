"""Run browser checks against the dedicated test DB, never the development data."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
import uvicorn

load_dotenv(Path(__file__).resolve().parents[1] / '.env.test')
url = os.environ.get('TEST_DATABASE_URL', '')
if not url or not make_url(url).database.endswith('_test') or make_url(url).drivername != 'mysql+pymysql':
    raise RuntimeError('Browser tests require a dedicated TEST_DATABASE_URL ending in _test')
os.environ['DATABASE_URL'] = url
os.environ['APP_ORIGIN'] = 'http://localhost:5173'
os.environ['JWT_SECRET'] = 'browser-test-only-' + 'a1b2c3d4' * 6
os.environ['APP_ENV'] = 'development'
os.environ['COOKIE_SECURE'] = 'false'
if __name__ == '__main__':
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000)
