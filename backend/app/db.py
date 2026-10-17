"""Database engine / session management."""

import logging
import time
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

log = logging.getLogger("celestial.db")

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    with SessionLocal() as session:
        yield session


def wait_for_db(retries: int = 30, delay: float = 1.0) -> None:
    """Block until PostgreSQL accepts connections (extra safety on top of
    the compose healthcheck, e.g. while init.sql is still running)."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM categories LIMIT 1"))
            log.info("Database is ready (attempt %d)", attempt)
            return
        except OperationalError as exc:
            log.warning("Database not ready (attempt %d/%d): %s", attempt, retries, exc.orig)
        except Exception as exc:  # e.g. table not created yet
            log.warning("Database schema not ready (attempt %d/%d): %s", attempt, retries, exc)
        time.sleep(delay)
    raise RuntimeError("Could not connect to the database")


def ping_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
