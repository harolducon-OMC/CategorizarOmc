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


def _engine_options(url) -> dict:
    """Pool de conexiones ajustado para PostgreSQL (Neon cierra conexiones inactivas)."""
    backend = url.get_backend_name() if hasattr(url, "get_backend_name") else str(url).split(":", 1)[0].split("+", 1)[0]
    options = {"pool_pre_ping": True}
    if backend == "postgresql":
        options.update(
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "300")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "20")),
            connect_args={"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10"))},
        )
    return options


_url = _database_url()
engine = create_engine(_url, **_engine_options(_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()