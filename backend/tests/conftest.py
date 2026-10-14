import json
import os
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_now
from app.db import get_db
from app.main import app
from app.models import Base
from app.ratelimit import limiter
from app.services.codeforces import CodeforcesClient, Throttle, get_codeforces_client

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
    if not {"engine", "db", "client"} & set(request.fixturenames):
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


@pytest.fixture(autouse=True)
def _no_rate_limit() -> Iterator[None]:
    """Auth endpoints are limited to 10/min per IP; only the dedicated test turns it on."""
    limiter.enabled = False
    limiter.reset()
    yield
    limiter.enabled = False


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str, password: str = "password123") -> dict[str, str]:
    """Register + log in; returns Authorization headers."""
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def user_a(client: TestClient) -> dict[str, str]:
    return register(client, "a@example.com")


@pytest.fixture
def user_b(client: TestClient) -> dict[str, str]:
    return register(client, "b@example.com")


@pytest.fixture
def set_now() -> Iterator[Callable[[str], None]]:
    """Pin the server clock, e.g. set_now("2026-10-14T12:00:00+00:00")."""

    def _set(iso: str) -> None:
        moment = datetime.fromisoformat(iso)
        app.dependency_overrides[get_now] = lambda: moment

    yield _set
    app.dependency_overrides.pop(get_now, None)


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class CfMock:
    """Stands in for codeforces.com: tests never touch the network."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []
        self.responses: dict[str, Any] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = request.url.path.rsplit("/", 1)[-1]
        response = self.responses[route]
        if isinstance(response, Exception):
            raise response
        if callable(response):
            result: httpx.Response = response(request)
            return result
        return httpx.Response(200, json=response)

    def client(self) -> CodeforcesClient:
        return CodeforcesClient(
            base_url="https://cf.test/api",
            throttle=Throttle(0),
            transport=httpx.MockTransport(self.handler),
            sleep=self.sleeps.append,
        )


@pytest.fixture
def cf() -> Iterator[CfMock]:
    mock = CfMock()
    mock.responses["user.status"] = load_fixture("cf_user_status.json")
    mock.responses["problemset.problems"] = load_fixture("cf_problemset.json")
    app.dependency_overrides[get_codeforces_client] = mock.client
    yield mock
    app.dependency_overrides.pop(get_codeforces_client, None)
