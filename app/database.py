from alembic import command
from alembic.config import Config
from fastapi import Request
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.config import ROOT


def build_engine(url):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False, "timeout": 20}
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def sqlite_settings(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def migrate(engine):
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def get_db(request: Request):
    with request.app.state.sessions() as db:
        # SQLite: захватываем write lock ДО чтения расписания. Другой запрос
        # дождётся commit, затем увидит уже добавленное занятие.
        if db.bind.dialect.name == "sqlite" and request.method not in {"GET", "HEAD", "OPTIONS"}:
            db.execute(text("BEGIN IMMEDIATE"))
        yield db


def session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)
