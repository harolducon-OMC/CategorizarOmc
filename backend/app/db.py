import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _database_url():
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        # Render entrega postgres:// o postgresql://; SQLAlchemy + psycopg v3 requiere postgresql+psycopg://
        if explicit_url.startswith("postgres://"):
            explicit_url = explicit_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif explicit_url.startswith("postgresql://"):
            explicit_url = explicit_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return explicit_url
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("DB_USER", "insights"),
        password=os.getenv("DB_PASSWORD", "change-this-local"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "insights"),
    )


engine = create_engine(_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()