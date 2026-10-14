from datetime import UTC, date, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Platform,
    Problem,
    ReviewCard,
    Solve,
    SolveSource,
    Tag,
    User,
)


def make_user(db: Session, email: str = "a@example.com") -> User:
    user = User(email=email, password_hash="x")
    db.add(user)
    db.commit()
    return user


def make_problem(db: Session, external_id: str = "1A") -> Problem:
    problem = Problem(platform=Platform.codeforces, external_id=external_id, title="t")
    db.add(problem)
    db.commit()
    return problem


def test_migration_matches_models(engine: Engine) -> None:
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_user_defaults_and_lowercase_check(db: Session) -> None:
    user = make_user(db)
    db.refresh(user)
    assert user.timezone == "Europe/Moscow"
    assert user.created_at is not None
    db.add(User(email="Upper@Example.com", password_hash="x"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_problem_unique_per_platform(db: Session) -> None:
    make_problem(db)
    db.add(Problem(platform=Platform.codeforces, external_id="1A", title="dup"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Problem(platform=Platform.leetcode, external_id="1A", title="other platform"))
    db.commit()


def test_solve_unique_and_cascade(db: Session) -> None:
    user = make_user(db)
    problem = make_problem(db)
    problem.tags = [Tag(name="dp"), Tag(name="graphs")]
    db.add(
        Solve(
            user_id=user.id,
            problem_id=problem.id,
            source=SolveSource.manual,
            solved_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db.add(ReviewCard(user_id=user.id, problem_id=problem.id, due_date=date(2026, 1, 2)))
    db.commit()

    db.add(
        Solve(
            user_id=user.id,
            problem_id=problem.id,
            source=SolveSource.manual,
            solved_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db.commit()
    assert db.scalar(select(func.count()).select_from(Solve)) == 0
    assert db.scalar(select(func.count()).select_from(ReviewCard)) == 0


def test_notes_length_constraint(db: Session) -> None:
    user = make_user(db)
    problem = make_problem(db)
    db.add(
        Solve(
            user_id=user.id,
            problem_id=problem.id,
            source=SolveSource.manual,
            solved_at=datetime(2026, 1, 1, tzinfo=UTC),
            notes="x" * 2001,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
