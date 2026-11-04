import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers.dependencies import Actor, current_actor
from app.core.database import engine, get_db
from app.core.security import (DUMMY_HASH, PREAUTH_COOKIE, SESSION_COOKIE, check_csrf, cookie,
                               csrf_for, decode, digest, encode, passwords, verify_password)
from app.models import AuthSession, RateBucket, User
from app.models.identity import utcnow
from app.schemas.identity import LoginInput, RegisterInput

router = APIRouter(prefix='/api/v1/auth', tags=['authentication'])


def user_view(user):
    return dict(id=user.id, display_name=user.display_name, email=user.email_normalized)


def limit(request, email):
    # Independent committed counters survive failed login transaction rollback.
    now = utcnow()
    for label, value, seconds, ceiling in [('ip', request.client.host, 60, 30), ('email', email, 900, 10)]:
        key = digest(f'{label}:{value}:{int(now.timestamp()) // seconds}')
        with Session(engine()) as db, db.begin():
            db.execute(delete(RateBucket).where(RateBucket.expires_at < now))
            stmt = insert(RateBucket).values(key=key, hits=1, expires_at=now + timedelta(seconds=seconds))
            db.execute(stmt.on_duplicate_key_update(hits=RateBucket.hits + 1))
            count = db.scalar(select(RateBucket.hits).where(RateBucket.key == key))
        if count > ceiling:
            raise HTTPException(429, 'Too many attempts; try again later', headers={'Retry-After': str(seconds)})


def preauth(request):
    payload = decode(request.cookies.get(PREAUTH_COOKIE, ''), 'preauth')
    check_csrf(request, payload['sid'])


def start_session(db, user, response):
    sid = secrets.token_urlsafe(32)
    csrf = csrf_for(sid)
    db.add(AuthSession(user_id=user.id, token_id_hash=digest(sid), csrf_token_hash=digest(csrf),
                       expires_at=utcnow() + timedelta(hours=8)))
    db.commit()
    cookie(response, SESSION_COOKIE, encode('session', sid, user.id), 8 * 3600)
    response.delete_cookie(PREAUTH_COOKIE, path='/api')
    return dict(user=user_view(user), csrf_token=csrf)


@router.get('/csrf')
def csrf(request: Request, response: Response, db: Session = Depends(get_db)):
    if request.cookies.get(SESSION_COOKIE):
        try:
            actor = current_actor(request, db)
            return {'csrf_token': csrf_for(actor.sid)}
        except HTTPException:
            response.delete_cookie(SESSION_COOKIE, path='/api')
    try:
        sid = decode(request.cookies.get(PREAUTH_COOKIE, ''), 'preauth')['sid']
    except HTTPException:
        sid = secrets.token_urlsafe(32)
    cookie(response, PREAUTH_COOKIE, encode('preauth', sid, hours=1 / 3), 1200)
    return {'csrf_token': csrf_for(sid)}


@router.post('/register', status_code=201)
def register(data: RegisterInput, request: Request, response: Response, db: Session = Depends(get_db)):
    preauth(request)
    email = str(data.email).lower()
    limit(request, email)
    user = User(email_normalized=email, display_name=data.display_name, password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.flush()
        return start_session(db, user, response)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Account could not be created; try signing in instead') from exc


@router.post('/login')
def login(data: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    preauth(request)
    email = str(data.email).lower()
    limit(request, email)
    user = db.scalar(select(User).where(User.email_normalized == email))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, data.password)
    if not valid or not user or user.disabled_at:
        raise HTTPException(401, 'Email or password is incorrect')
    if passwords.check_needs_rehash(user.password_hash):
        user.password_hash = passwords.hash(data.password)
    return start_session(db, user, response)


@router.get('/me')
def me(actor: Actor = Depends(current_actor)):
    return user_view(actor.user)


@router.post('/logout', status_code=204)
def logout(response: Response, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    actor.session.revoked_at = utcnow()
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path='/api')
    response.delete_cookie(PREAUTH_COOKIE, path='/api')
