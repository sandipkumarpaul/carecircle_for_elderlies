from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import SESSION_COOKIE, check_csrf, decode, digest
from app.models import AuthSession, User
from app.models.identity import utcnow


@dataclass
class Actor:
    user: User
    session: AuthSession
    sid: str


def current_actor(request: Request, db: Session = Depends(get_db)):
    payload = decode(request.cookies.get(SESSION_COOKIE, ''), 'session')
    session = db.scalar(select(AuthSession).where(AuthSession.token_id_hash == digest(payload['sid'])))
    if not session or session.revoked_at or session.expires_at <= utcnow() or session.user_id != payload['sub']:
        raise HTTPException(401, 'Session expired; sign in again')
    user = db.get(User, session.user_id)
    if not user or user.disabled_at:
        raise HTTPException(401, 'Session expired; sign in again')
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        check_csrf(request, payload['sid'], session.csrf_token_hash)
    return Actor(user, session, payload['sid'])
