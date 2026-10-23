import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import COOKIE_NAME, SESSION_DAYS
from app.database import get_db
from app.models import LoginSession, User, utcnow


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def verify_password(password, encoded):
    try:
        _, rounds, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db: Session, user: User, request: Request, response: Response):
    token = secrets.token_urlsafe(32)
    record = LoginSession(user_id=user.id, token_hash=token_hash(token),
                          csrf_token=secrets.token_urlsafe(32),
                          expires_at=utcnow() + timedelta(days=SESSION_DAYS))
    db.add(record)
    db.commit()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict",
                        secure=request.app.state.cookie_secure, max_age=SESSION_DAYS * 86400)
    return {"user": public_user(user), "csrf_token": record.csrf_token}


def public_user(user):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def current_user(request: Request, db: Session = Depends(get_db),
                 csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
    token = request.cookies.get(COOKIE_NAME)
    record = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(token))) if token else None
    if not record or record.expires_at <= utcnow():
        raise HTTPException(401, "Войдите в аккаунт")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not hmac.compare_digest(csrf_header or "", record.csrf_token):
            raise HTTPException(403, "Обновите страницу и повторите действие")
    request.state.login_session = record
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(401, "Аккаунт не найден")
    return user


def teacher_only(user: User = Depends(current_user)):
    if user.role != "teacher":
        raise HTTPException(403, "Это действие доступно только репетитору")
    return user
