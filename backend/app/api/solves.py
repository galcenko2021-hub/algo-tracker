from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession, Now, local_today
from app.models import (
    AttemptStat,
    Platform,
    Problem,
    ReviewCard,
    Solve,
    SolveSource,
    Tag,
    User,
    problem_tags,
)
from app.schemas.solves import SolveCreate, SolveOut, SolvePage, SolvePatch
from app.services.solves import (
    DuplicateSolveError,
    create_solve,
    get_or_create_problem,
    get_or_create_tags,
    user_zone,
)

router = APIRouter(prefix="/solves", tags=["solves"])
tags_router = APIRouter(prefix="/tags", tags=["solves"])


def _get_own_solve(db: Session, user: User, solve_id: int) -> Solve:
    solve = db.scalar(select(Solve).where(Solve.id == solve_id, Solve.user_id == user.id))
    if solve is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Решение не найдено")
    return solve


def _reject_future(solved_at: datetime | None, now: Now) -> None:
    # one day of slack covers clients in time zones ahead of the server
    if solved_at is not None and solved_at > now + timedelta(days=1):
        raise HTTPException(422, "Дата решения в будущем")


@router.post("", response_model=SolveOut, status_code=status.HTTP_201_CREATED)
def add_solve(body: SolveCreate, user: CurrentUser, db: DbSession, now: Now) -> Solve:
    _reject_future(body.solved_at, now)
    problem = get_or_create_problem(
        db,
        platform=body.platform,
        external_id=body.external_id,
        title=body.title,
        url=body.url,
        rating=body.rating,
        tags=body.tags,
    )
    try:
        solve = create_solve(
            db,
            user,
            problem=problem,
            solved_at=body.solved_at,
            source=SolveSource.manual,
            time_spent_min=body.time_spent_min,
            notes=body.notes,
            today=local_today(now, user),
            now=now,
        )
        db.commit()
    except DuplicateSolveError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Эта задача уже добавлена") from None
    db.refresh(solve)
    return solve


def _day_bounds(day: date, user: User, *, end: bool) -> datetime:
    boundary = day + timedelta(days=1) if end else day
    return datetime.combine(boundary, time.min, tzinfo=user_zone(user)).astimezone(UTC)


@router.get("", response_model=SolvePage)
def list_solves(
    user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    platform: Platform | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SolvePage:
    conditions: list[ColumnElement[bool]] = [Solve.user_id == user.id]
    if date_from is not None:
        conditions.append(Solve.solved_at >= _day_bounds(date_from, user, end=False))
    if date_to is not None:
        conditions.append(Solve.solved_at < _day_bounds(date_to, user, end=True))
    if platform is not None:
        conditions.append(Problem.platform == platform)
    if q and q.strip():
        needle = q.strip()
        conditions.append(
            or_(
                Problem.title.icontains(needle, autoescape=True),
                Problem.external_id.icontains(needle, autoescape=True),
            )
        )
    for name in {t.strip().lower() for t in tag or [] if t.strip()}:
        conditions.append(
            exists()
            .where(problem_tags.c.problem_id == Problem.id)
            .where(problem_tags.c.tag_id == Tag.id)
            .where(Tag.name == name)
        )

    total = db.scalar(
        select(func.count())
        .select_from(Solve)
        .join(Problem, Solve.problem_id == Problem.id)
        .where(*conditions)
    )
    rows = db.scalars(
        select(Solve)
        .join(Problem, Solve.problem_id == Problem.id)
        .where(*conditions)
        .order_by(Solve.solved_at.desc(), Solve.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).unique()
    return SolvePage(
        items=[SolveOut.model_validate(s) for s in rows],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.patch("/{solve_id}", response_model=SolveOut)
def patch_solve(
    solve_id: int, body: SolvePatch, user: CurrentUser, db: DbSession, now: Now
) -> Solve:
    _reject_future(body.solved_at, now)
    solve = _get_own_solve(db, user, solve_id)
    fields = body.model_fields_set
    if body.solved_at is not None:
        solve.solved_at = body.solved_at
    if "time_spent_min" in fields:
        solve.time_spent_min = body.time_spent_min
    if "notes" in fields:
        solve.notes = body.notes

    problem = solve.problem
    if {"title", "url", "rating", "tags"} & fields:
        current_tags = [t.name for t in problem.tags]
        title = body.title if body.title is not None else problem.title
        url = body.url if "url" in fields else problem.url
        rating = body.rating if "rating" in fields else problem.rating
        tags = body.tags if body.tags is not None else current_tags
        changed = (title, url, rating, sorted(tags)) != (
            problem.title,
            problem.url,
            problem.rating,
            sorted(current_tags),
        )
        if changed:
            shared = exists().where(Solve.problem_id == problem.id, Solve.user_id != user.id)
            shared_attempts = exists().where(
                AttemptStat.problem_id == problem.id, AttemptStat.user_id != user.id
            )
            if db.scalar(select(shared | shared_attempts)):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Задача общая для нескольких пользователей: "
                    "можно менять только дату, время и заметку",
                )
            problem.title = title
            problem.url = url
            problem.rating = rating
            problem.tags = get_or_create_tags(db, tags)
    db.commit()
    db.refresh(solve)
    return solve


@router.delete("/{solve_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_solve(solve_id: int, user: CurrentUser, db: DbSession) -> Response:
    solve = _get_own_solve(db, user, solve_id)
    card = db.scalar(
        select(ReviewCard).where(
            ReviewCard.user_id == user.id, ReviewCard.problem_id == solve.problem_id
        )
    )
    if card is not None:
        db.delete(card)  # review_log rows go with it (ON DELETE CASCADE)
    db.delete(solve)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@tags_router.get("", response_model=list[str])
def autocomplete_tags(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str, Query(max_length=64)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[str]:
    stmt = (
        select(Tag.name)
        .join(problem_tags, problem_tags.c.tag_id == Tag.id)
        .join(Solve, Solve.problem_id == problem_tags.c.problem_id)
        .where(Solve.user_id == user.id)
        .group_by(Tag.name)
        .order_by(func.count().desc(), Tag.name)
        .limit(limit)
    )
    if q.strip():
        stmt = stmt.where(Tag.name.icontains(q.strip().lower(), autoescape=True))
    return list(db.scalars(stmt))
