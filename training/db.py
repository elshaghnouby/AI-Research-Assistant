"""Engine and session factory.

SQLite by default so the app runs with no infrastructure. Point DATABASE_URL at
Postgres (postgresql+psycopg://...) and nothing else changes.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = f"sqlite:///{ROOT / 'data' / 'training.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_URL)

if DATABASE_URL.startswith("sqlite"):
    (ROOT / "data").mkdir(exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def session() -> Session:
    return SessionLocal()
