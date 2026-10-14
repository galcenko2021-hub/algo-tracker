import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://algo:algo@localhost:5432/algo_test"
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Real PostgreSQL; schema is built by the Alembic migrations (so they are tested too)."""
    eng = create_engine(TEST_DATABASE_URL)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _clean_db(request: pytest.FixtureRequest) -> Iterator[None]:
    """Truncate every table before a test that touches the DB."""
    if "engine" not in request.fixturenames and "db" not in request.fixturenames:
        yield
        return
    engine: Engine = request.getfixturevalue("engine")
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
