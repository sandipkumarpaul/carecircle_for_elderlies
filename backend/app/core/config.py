import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


@lru_cache
def settings():
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
    secret = os.environ.get('JWT_SECRET', '')
    if len(secret) < 32 or secret.startswith('REPLACE_'):
        raise RuntimeError('Set JWT_SECRET to a random secret of at least 32 characters in backend/.env')
    database = os.environ.get('DATABASE_URL', '')
    if not database.startswith('mysql+pymysql://'):
        raise RuntimeError('DATABASE_URL must use mysql+pymysql://')
    origin = os.environ.get('APP_ORIGIN', 'http://localhost:5173').rstrip('/')
    secure = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'
    if os.environ.get('APP_ENV', 'development') != 'development' and (not secure or not origin.startswith('https://')):
        raise RuntimeError('Non-development environments require HTTPS and secure cookies')
    return dict(secret=secret, database=database, origin=origin, secure=secure,
                issuer='carecircle', audience='carecircle-web')
