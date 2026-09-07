# app/db/session.py

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

connect_args = {}

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    connect_args["check_same_thread"] = False

    # Analyzer threads commit from outside the request cycle, so the default
    # 5s-lock-then-fail behaviour is not enough.
    connect_args["timeout"] = 15.0

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, connection_record):
        """
        WAL lets the API read while analyzer threads write, which is what
        makes several cameras writing events to one SQLite file viable on an
        edge device. Without this, concurrent writers raise
        "database is locked" under load.
        """
        cursor = dbapi_connection.cursor()

        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()