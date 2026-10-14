from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ReviewCard, ReviewLog, Solve, User
from scripts.seed_demo import DEMO_EMAIL, DEMO_PASSWORD, seed

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_seed_builds_synthetic_history(db: Session) -> None:
    user = seed(db, now=NOW)
    solves = list(db.scalars(select(Solve).where(Solve.user_id == user.id)).unique())
    assert len(solves) > 60
    oldest = min(s.solved_at for s in solves)
    assert NOW - oldest > timedelta(days=150)  # roughly six months of history
    assert max(s.solved_at for s in solves) <= NOW
    assert all(s.problem.title.startswith("[demo]") for s in solves)  # clearly marked synthetic

    overdue = db.scalars(
        select(ReviewCard).where(ReviewCard.user_id == user.id, ReviewCard.due_date < NOW.date())
    ).all()
    assert len(overdue) >= 5
    assert db.scalar(select(func.count()).select_from(ReviewLog)) > 0


def test_seed_is_repeatable(db: Session) -> None:
    seed(db, now=NOW)
    first = db.scalar(select(func.count()).select_from(Solve))
    seed(db, now=NOW)
    assert db.scalar(select(func.count()).select_from(User).where(User.email == DEMO_EMAIL)) == 1
    assert db.scalar(select(func.count()).select_from(Solve)) == first


def test_demo_user_can_log_in_and_has_data(client: TestClient, db: Session) -> None:
    seed(db)
    res = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert res.status_code == 200
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    summary = client.get("/api/stats/summary", headers=headers).json()
    assert summary["total"] > 60 and summary["current_streak"] >= 5
    assert client.get("/api/reviews/due", headers=headers).json()["count"] >= 5
    topics = client.get("/api/stats/topics", headers=headers).json()
    assert {t["tag"] for t in topics} >= {"dp", "greedy", "graphs"}
