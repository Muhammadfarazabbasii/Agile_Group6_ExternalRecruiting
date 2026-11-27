"""Database connection. SQLite file for now; set DATABASE_URL to use PostgreSQL later."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker



def normalize_database_url(url: str) -> str:
    """Cloud providers give postgres:// or postgresql:// URLs. SQLAlchemy needs to know the driver (psycopg 3)."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./group6.db"))

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
# pool_pre_ping: a cloud database closes idle connections, so test each one before use.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=not is_sqlite)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Gives each request its own database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
