"""Loads everything the recommenders need from the database."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AttemptStat, CfCatalogEntry, Platform, Problem, Solve, User
from app.services import stats_db
from app.services.recommender.base import Candidate, UserContext, estimate_level
from app.services.recommender.ml import AttemptSample


def load_candidates(db: Session) -> list[Candidate]:
    return [
        Candidate(
            external_id=e.external_id,
            title=e.title,
            url=e.url,
            rating=e.rating,
            tags=list(e.tags),
            solved_count=e.solved_count,
        )
        for e in db.scalars(select(CfCatalogEntry))
    ]


def load_context(db: Session, user: User) -> UserContext:
    recent_ratings = list(
        db.scalars(
            select(Problem.rating)
            .join(Solve, Solve.problem_id == Problem.id)
            .where(Solve.user_id == user.id, Problem.rating.is_not(None))
            .order_by(Solve.solved_at.desc(), Solve.id.desc())
            .limit(20)
        )
    )
    solved_ids = frozenset(
        db.scalars(
            select(Problem.external_id)
            .join(Solve, Solve.problem_id == Problem.id)
            .where(Solve.user_id == user.id, Problem.platform == Platform.codeforces)
        )
    )
    return UserContext(
        level=estimate_level([r for r in recent_ratings if r is not None]),
        total_solved=stats_db.total_solves(db, user),
        tags={a.tag: a for a in stats_db.tag_aggregates(db, user)},
        solved_ids=solved_ids,
    )


def load_attempt_samples(
    db: Session, user: User, candidates: list[Candidate]
) -> list[AttemptSample]:
    """Attempts with a known rating; popularity comes from the catalog (0 if unknown)."""
    popularity = {c.external_id: c.solved_count for c in candidates}
    rows = db.execute(
        select(AttemptStat, Problem)
        .join(Problem, Problem.id == AttemptStat.problem_id)
        .where(
            AttemptStat.user_id == user.id,
            Problem.platform == Platform.codeforces,
            Problem.rating.is_not(None),
        )
    ).all()
    return [
        AttemptSample(
            rating=problem.rating or 0,
            tags=[t.name for t in problem.tags],
            solved_count=popularity.get(problem.external_id, 0),
            solved=attempt.solved,
            first_attempt_at=attempt.first_attempt_at,
        )
        for attempt, problem in rows
    ]


def tag_vocabulary(candidates: list[Candidate]) -> list[str]:
    return sorted({tag for c in candidates for tag in c.tags})
