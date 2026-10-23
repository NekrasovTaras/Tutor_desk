import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import COOKIE_NAME
from app.database import get_db
from app.models import LoginSession, User
from app.schemas import Login, PasswordChange, Register
from app.security import current_user, hash_password, public_user, start_session, verify_password

router = APIRouter(prefix="/api/auth", tags=["Вход и аккаунт"])


def limit_attempts(request: Request):
    key = request.client.host if request.client else "local"
    now = time.monotonic()
    # Учебный лимитер одного процесса. Для нескольких workers нужен общий Redis.
    with request.app.state.attempts_lock:
        attempts = request.app.state.attempts
        for ip in list(attempts):
            while attempts[ip] and attempts[ip][0] < now - 600:
                attempts[ip].popleft()
            if not attempts[ip]:
                del attempts[ip]
        queue = attempts.setdefault(key, deque())
        if len(queue) >= 30:
            raise HTTPException(429, "Слишком много попыток. Попробуйте через 10 минут.")
        queue.append(now)


@router.post("/register", status_code=201)
def register(data: Register, request: Request, response: Response, db: Session = Depends(get_db)):
    limit_attempts(request)
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(409, "Этот email уже используется")
    user = User(email=data.email, name=data.name, password_hash=hash_password(data.password), role="teacher")
    db.add(user)
    db.flush()
    return start_session(db, user, request, response)


@router.post("/login")
def login(data: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    limit_attempts(request)
    user = db.scalar(select(User).where(User.email == data.email))
    if not user:
        hash_password(data.password)  # одинаковая дорогая операция для неизвестного email
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    return start_session(db, user, request, response)


@router.get("/me")
def me(request: Request, user: User = Depends(current_user)):
    return {"user": public_user(user), "csrf_token": request.state.login_session.csrf_token}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(request.state.login_session)
    db.commit()
    response.delete_cookie(COOKIE_NAME)


@router.post("/password", status_code=204)
def change_password(data: PasswordChange, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Текущий пароль неверен")
    user.password_hash = hash_password(data.new_password)
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    db.commit()
    response.delete_cookie(COOKIE_NAME)
