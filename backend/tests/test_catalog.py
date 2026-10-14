from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CfCatalogEntry
from app.services.catalog import ensure_catalog, is_fresh, refresh_catalog
from app.services.codeforces import CodeforcesUnavailable
from tests.conftest import CfMock

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_refresh_stores_problems_with_solved_counts(cf: CfMock, db: Session) -> None:
    assert refresh_catalog(db, cf.client(), NOW) == 4  # gym problem excluded
    entries = {e.external_id: e for e in db.scalars(select(CfCatalogEntry))}
    assert set(entries) == {"1700A", "1700B", "1701C", "1800D"}
    a = entries["1700A"]
    assert (a.title, a.rating, a.solved_count) == ("Optimal Path", 800, 50000)
    assert a.tags == ["greedy", "math"]
    assert a.url == "https://codeforces.com/problemset/problem/1700/A"
    assert entries["1701C"].rating is None


def test_refresh_is_repeatable_and_drops_removed_problems(cf: CfMock, db: Session) -> None:
    refresh_catalog(db, cf.client(), NOW)
    payload = cf.responses["problemset.problems"]
    payload["result"]["problems"] = payload["result"]["problems"][:2]
    refresh_catalog(db, cf.client(), NOW + timedelta(days=2))
    assert {e.external_id for e in db.scalars(select(CfCatalogEntry))} == {"1700A", "1700B"}


def test_ttl_controls_refresh(cf: CfMock, db: Session) -> None:
    assert not is_fresh(db, NOW)
    assert ensure_catalog(db, cf.client(), NOW) is True
    assert is_fresh(db, NOW + timedelta(hours=23, minutes=59))
    assert ensure_catalog(db, cf.client(), NOW + timedelta(hours=23)) is False
    assert len(cf.requests) == 1
    assert ensure_catalog(db, cf.client(), NOW + timedelta(hours=25)) is True
    assert len(cf.requests) == 2


def test_stale_catalog_is_used_when_codeforces_is_down(cf: CfMock, db: Session) -> None:
    ensure_catalog(db, cf.client(), NOW)
    cf.responses["problemset.problems"] = lambda request: httpx.Response(503)
    assert ensure_catalog(db, cf.client(), NOW + timedelta(days=3)) is False
    assert db.scalar(select(CfCatalogEntry.external_id).limit(1)) is not None


def test_empty_catalog_and_codeforces_down_raises(cf: CfMock, db: Session) -> None:
    cf.responses["problemset.problems"] = lambda request: httpx.Response(503)
    with pytest.raises(CodeforcesUnavailable):
        ensure_catalog(db, cf.client(), NOW)
