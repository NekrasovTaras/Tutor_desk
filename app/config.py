import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(ROOT / 'data' / 'tutordesk.db').as_posix()}")
COOKIE_NAME = "tutordesk_session"
SESSION_DAYS = 7
