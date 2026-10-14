"""Local copy of the Codeforces problemset used by the recommenders (refreshed on demand)."""

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import CfCatalogEntry
from app.services.codeforces import (
    GYM_CONTEST_ID_FROM,
    CodeforcesClient,
    CodeforcesError,
)

CATALOG_TTL = timedelta(hours=24)
_CHUNK = 2000


def is_fresh(db: Session, now: datetime) -> bool:
    latest = db.scalar(select(func.max(CfCatalogEntry.fetched_at)))
    return latest is not None and now - latest < CATALOG_TTL


def refresh_catalog(db: Session, client: CodeforcesClient, now: datetime) -> int:
    """Download the problemset and replace the catalog. Returns the number of entries."""
    problemset = client.problemset()
    solved_counts = {(s.contestId, s.index): s.solvedCount for s in problemset.problemStatistics}
    rows = []
    for problem in problemset.problems:
        if problem.contestId is None or problem.contestId >= GYM_CONTEST_ID_FROM:
            continue
        external_id = f"{problem.contestId}{problem.index}"
        rows.append(
            {
                "external_id": external_id,
                "title": problem.name[:500],
                "url": (
                    f"https://codeforces.com/problemset/problem/{problem.contestId}/{problem.index}"
                ),
                "rating": problem.rating,
                "tags": sorted({t.strip().lower() for t in problem.tags if t.strip()}),
                "solved_count": solved_counts.get((problem.contestId, problem.index), 0),
                "fetched_at": now,
            }
        )
    for start in range(0, len(rows), _CHUNK):
        stmt = pg_insert(CfCatalogEntry).values(rows[start : start + _CHUNK])
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=["external_id"],
                set_={
                    col: getattr(stmt.excluded, col)
                    for col in ("title", "url", "rating", "tags", "solved_count", "fetched_at")
                },
            )
        )
    db.execute(delete(CfCatalogEntry).where(CfCatalogEntry.fetched_at < now))
    db.commit()
    return len(rows)


def ensure_catalog(db: Session, client: CodeforcesClient, now: datetime) -> bool:
    """Refresh when older than the TTL. Returns True if a refresh happened.

    If Codeforces is unreachable but an older catalog exists, the stale copy is used.
    """
    if is_fresh(db, now):
        return False
    try:
        refresh_catalog(db, client, now)
    except CodeforcesError:
        db.rollback()
        if db.scalar(select(func.count()).select_from(CfCatalogEntry)):
            return False
        raise
    return True
