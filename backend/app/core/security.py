import hashlib
import hmac
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request

from app.core.config import settings
from app.models.identity import utcnow

passwords = PasswordHasher()
DUMMY_HASH = passwords.hash('unused-' + secrets.token_urlsafe(32))
SESSION_COOKIE = 'carecircle_session'
PREAUTH_COOKIE = 'carecircle_preauth'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for(sid):
    return hmac.new(settings()['secret'].encode(), ('csrf:' + sid).encode(), hashlib.sha256).hexdigest()


def encode(kind, sid, subject='', hours=8):
    now = utcnow()
    config = settings()
    return jwt.encode(dict(sub=subject, sid=sid, kind=kind, iat=now, exp=now + timedelta(hours=hours),
                           iss=config['issuer'], aud=config['audience']), config['secret'], algorithm='HS256')


def decode(token, kind):
    try:
        config = settings()
        payload = jwt.decode(token, config['secret'], algorithms=['HS256'], issuer=config['issuer'],
                             audience=config['audience'], options={'require': ['sub', 'sid', 'kind', 'iat', 'exp', 'iss', 'aud']})
        if payload['kind'] != kind or not isinstance(payload['sid'], str):
            raise ValueError('Wrong token kind')
        return payload
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise HTTPException(401, 'Sign in to continue') from exc


def cookie(response, name, value, seconds):
    response.set_cookie(name, value, max_age=seconds, httponly=True, secure=settings()['secure'],
                        samesite='lax', path='/api')


def check_origin(request: Request):
    if request.headers.get('origin') != settings()['origin']:
        raise HTTPException(403, 'Request origin is not allowed')


def check_csrf(request, sid, stored_hash=None):
    check_origin(request)
    supplied = request.headers.get('x-csrf-token', '')
    expected = csrf_for(sid)
    if not hmac.compare_digest(supplied, expected) or (stored_hash and not hmac.compare_digest(digest(supplied), stored_hash)):
        raise HTTPException(403, 'Security token expired; reload and try again')


def verify_password(encoded, plain):
    try:
        return passwords.verify(encoded, plain)
    except (VerificationError, InvalidHashError):
        return False
