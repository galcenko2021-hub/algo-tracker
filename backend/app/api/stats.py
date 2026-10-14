from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, DbSession, Now, local_today
from app.schemas.stats import HeatmapDay, SummaryOut, TopicOut
from app.services import stats, stats_db

router = APIRouter(prefix="/stats", tags=["stats"])

MAX_HEATMAP_DAYS = 3660


@router.get("/summary", response_model=SummaryOut)
def get_summary(user: CurrentUser, db: DbSession, now: Now) -> SummaryOut:
    summary = stats.summarize(stats_db.daily_counts(db, user), local_today(now, user))
    return SummaryOut(**summary.__dict__)


@router.get("/heatmap", response_model=list[HeatmapDay])
def get_heatmap(
    user: CurrentUser,
    db: DbSession,
    now: Now,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> list[HeatmapDay]:
    end = date_to or local_today(now, user)
    start = date_from or end - timedelta(days=364)
    if start > end:
        raise HTTPException(422, "Параметр from позже to")
    if (end - start).days >= MAX_HEATMAP_DAYS:
        raise HTTPException(422, "Слишком большой период")
    series = stats.build_heatmap(stats_db.daily_counts(db, user), start, end)
    return [HeatmapDay(date=d, count=c) for d, c in series]


@router.get("/topics", response_model=list[TopicOut])
def get_topics(user: CurrentUser, db: DbSession) -> list[TopicOut]:
    topics = stats.topic_stats(stats_db.tag_aggregates(db, user), stats_db.total_solves(db, user))
    return [TopicOut(**t.__dict__) for t in topics]
