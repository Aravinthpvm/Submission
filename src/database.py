import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _normalize_database_url(raw_url: str) -> str:
    # Render/Postgres URLs may use postgres:// which SQLAlchemy does not accept directly.
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+psycopg2://", 1)

    # Neon and many managed Postgres providers require SSL.
    if raw_url.startswith("postgresql+psycopg2://") and "sslmode=" not in raw_url:
        separator = "&" if "?" in raw_url else "?"
        raw_url = f"{raw_url}{separator}sslmode=require"

    return raw_url


DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./skillbridge.db"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
