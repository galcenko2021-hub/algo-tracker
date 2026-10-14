"""Database loaders that feed the pure functions in `app.services.stats`."""

from collections import Counter, defaultdict
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Problem, ReviewCard, ReviewLog, Solve, Tag, User, problem_tags
from app.services.stats import TagAggregate


def daily_counts(db: Session, user: User) -> dict[date, int]:
    """Number of solves per *local* date of the user.

    Grouping happens in Python (zoneinfo) rather than with `AT TIME ZONE` in SQL, so the result
    does not depend on the time zone database installed on the PostgreSQL server.
    """
    zone = ZoneInfo(user.timezone)
    counts: Counter[date] = Counter()
    for moment in db.scalars(select(Solve.solved_at).where(Solve.user_id == user.id)):
        counts[moment.astimezone(zone).date()] += 1
    return dict(counts)


def total_solves(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(Solve).where(Solve.user_id == user.id)) or 0


def tag_aggregates(db: Session, user: User) -> list[TagAggregate]:
    solved_rows = db.execute(
        select(
            Tag.name,
            func.count(),
            func.coalesce(func.sum(Problem.rating), 0),
            func.count(Problem.rating),
            func.max(Solve.solved_at),
        )
        .select_from(Solve)
        .join(Problem, Problem.id == Solve.problem_id)
        .join(problem_tags, problem_tags.c.problem_id == Problem.id)
        .join(Tag, Tag.id == problem_tags.c.tag_id)
        .where(Solve.user_id == user.id)
        .group_by(Tag.name)
    ).all()

    quality: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
    quality_rows = db.execute(
        select(Tag.name, func.sum(ReviewLog.quality), func.count())
        .select_from(ReviewLog)
        .join(ReviewCard, ReviewCard.id == ReviewLog.card_id)
        .join(problem_tags, problem_tags.c.problem_id == ReviewCard.problem_id)
        .join(Tag, Tag.id == problem_tags.c.tag_id)
        .where(ReviewCard.user_id == user.id)
        .group_by(Tag.name)
    ).all()
    for name, q_sum, q_count in quality_rows:
        quality[name] = (float(q_sum), int(q_count))

    return [
        TagAggregate(
            tag=name,
            solved=solved,
            rating_sum=int(rating_sum or 0),
            rating_count=rating_count,
            last_solved_at=last,
            quality_sum=quality[name][0],
            quality_count=quality[name][1],
        )
        for name, solved, rating_sum, rating_count, last in solved_rows
    ]
