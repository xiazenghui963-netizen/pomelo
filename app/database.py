from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=8000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_tasks_skill_id():
    """轻量迁移：tasks 表补充 skill_id 字段（旧库无该列）。"""
    from sqlalchemy import text

    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(tasks)"))]
        if "skill_id" in cols:
            return
        conn.execute(text("ALTER TABLE tasks ADD COLUMN skill_id VARCHAR(64)"))
        conn.commit()


def _migrate_user_material():
    """轻量迁移：老库 user_material 表缺少 doc_type/source_name/is_enabled 列（模型早已有，老库未补）。"""
    from sqlalchemy import text

    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(user_material)"))]
        if "doc_type" not in cols:
            conn.execute(text("ALTER TABLE user_material ADD COLUMN doc_type VARCHAR(24) NOT NULL DEFAULT 'reference_context'"))
        if "source_name" not in cols:
            conn.execute(text("ALTER TABLE user_material ADD COLUMN source_name VARCHAR(128) NOT NULL DEFAULT ''"))
        if "is_enabled" not in cols:
            conn.execute(text("ALTER TABLE user_material ADD COLUMN is_enabled BOOLEAN NOT NULL DEFAULT 1"))
        conn.commit()


def init_db():
    from . import models  # noqa: F401
    from .services.seed import seed_admin

    Base.metadata.create_all(bind=engine)
    _migrate_tasks_skill_id()
    _migrate_user_material()
    seed_admin()