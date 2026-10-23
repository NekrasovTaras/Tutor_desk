import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.config import DATABASE_URL, ROOT
from app.database import build_engine, migrate, session_factory
from app.routers import auth, workspace


def create_app(database_url=None):
    (ROOT / "data").mkdir(exist_ok=True)
    engine = build_engine(database_url or DATABASE_URL)

    @asynccontextmanager
    async def lifespan(application):
        migrate(engine)
        yield
        engine.dispose()

    app = FastAPI(title="TutorDesk API", version="0.1.0", lifespan=lifespan,
                  description="Ученики, занятия и домашние задания. Войдите через интерфейс, затем используйте API с cookie и X-CSRF-Token.")
    app.state.engine = engine
    app.state.sessions = session_factory(engine)
    app.state.cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    app.state.attempts = {}
    app.state.attempts_lock = threading.Lock()

    @app.middleware("http")
    async def browser_protection(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            expected = str(request.base_url).rstrip("/")
            if origin and origin != expected:
                return JSONResponse({"detail": "Запрос с другого сайта отклонён"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        # Swagger использует внешние скрипты; интерфейс приложения — только локальные.
        if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, error):
        return JSONResponse({"detail": "Данные конфликтуют с существующей записью"}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Не возвращаем исходный input: в нём может быть пароль.
        errors = [{"field": ".".join(map(str, e["loc"][1:])), "message": e["msg"]} for e in error.errors()]
        return JSONResponse({"detail": "Проверьте заполнение полей", "errors": errors}, status_code=422)

    app.include_router(auth.router)
    app.include_router(workspace.router)
    app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "app" / "static" / "index.html")

    @app.get("/health", tags=["Служебное"])
    def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
