"""DB-aware helpers for creating problems, tags, solves and their review cards."""

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Platform, Problem, ReviewCard, Solve, SolveSource, Tag, User

_CF_ID = re.compile(r"^(\d+)([A-Za-z]\d*)$")
_SPACES = re.compile(r"\s+")


class DuplicateSolveError(Exception):
    pass


def user_zone(user: User) -> ZoneInfo:
    return ZoneInfo(user.timezone)


def local_date(moment: datetime, zone: ZoneInfo) -> date:
    return moment.astimezone(zone).date()


def normalize_title(title: str) -> str:
    return _SPACES.sub(" ", title.strip()).casefold()


def generate_external_id(title: str) -> str:
    """Stable id for problems without a platform id: derived from the normalized title."""
    digest = hashlib.sha1(normalize_title(title).encode("utf-8")).hexdigest()[:16]
    return f"t-{digest}"


def codeforces_url(external_id: str) -> str | None:
    match = _CF_ID.match(external_id)
    if match is None:
        return None
    return f"https://codeforces.com/problemset/problem/{match.group(1)}/{match.group(2).upper()}"


def first_review_date(solved_local: date, today: date) -> date:
    """First review is due the day after solving, but never in the past."""
    return max(solved_local + timedelta(days=1), today)


def get_or_create_tags(db: Session, names: Iterable[str]) -> list[Tag]:
    wanted = sorted(set(names))
    if not wanted:
        return []
    db.execute(pg_insert(Tag).values([{"name": n} for n in wanted]).on_conflict_do_nothing())
    return list(db.scalars(select(Tag).where(Tag.name.in_(wanted)).order_by(Tag.name)))


def get_or_create_problem(
    db: Session,
    *,
    platform: Platform,
    external_id: str | None,
    title: str,
    url: str | None,
    rating: int | None,
    tags: list[str],
) -> Problem:
    """Problems are shared between users; an existing problem is reused untouched."""
    ext_id = external_id or generate_external_id(title)
    if url is None and platform is Platform.codeforces:
        url = codeforces_url(ext_id)
    inserted_id = db.scalar(
        pg_insert(Problem)
        .values(platform=platform, external_id=ext_id, title=title, url=url, rating=rating)
        .on_conflict_do_nothing(index_elements=["platform", "external_id"])
        .returning(Problem.id)
    )
    problem = db.scalars(
        select(Problem).where(Problem.platform == platform, Problem.external_id == ext_id)
    ).one()
    if inserted_id is not None and tags:
        problem.tags = get_or_create_tags(db, tags)
    return problem


def create_solve(
    db: Session,
    user: User,
    *,
    problem: Problem,
    solved_at: datetime | None,
    source: SolveSource,
    time_spent_min: int | None = None,
    notes: str | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> Solve:
    """Add a solve and its review card. Raises DuplicateSolveError if already solved."""
    exists = db.scalar(
        select(Solve.id).where(Solve.user_id == user.id, Solve.problem_id == problem.id)
    )
    if exists is not None:
        raise DuplicateSolveError
    zone = user_zone(user)
    moment = solved_at or now or datetime.now(UTC)
    today = today or (now or datetime.now(UTC)).astimezone(zone).date()
    solve = Solve(
        user_id=user.id,
        problem_id=problem.id,
        solved_at=moment,
        source=source,
        time_spent_min=time_spent_min,
        notes=notes,
    )
    db.add(solve)
    card_exists = db.scalar(
        select(ReviewCard.id).where(
            ReviewCard.user_id == user.id, ReviewCard.problem_id == problem.id
        )
    )
    if card_exists is None:
        db.add(
            ReviewCard(
                user_id=user.id,
                problem_id=problem.id,
                ease=2.5,
                interval_days=0,
                repetitions=0,
                lapses=0,
                due_date=first_review_date(local_date(moment, zone), today),
            )
        )
    return solve
