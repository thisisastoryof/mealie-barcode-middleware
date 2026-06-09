from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """Add columns introduced after initial schema (idempotent)."""
    insp = inspect(engine)
    if "api_tokens" in insp.get_table_names():
        columns = {c["name"] for c in insp.get_columns("api_tokens")}
        if "token_prefix" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE api_tokens ADD COLUMN token_prefix VARCHAR(8)"))
