from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ReviewCard, ReviewLog

Headers = dict[str, str]
SetNow = Callable[[str], None]


def add(
    client: TestClient, headers: Headers, ext_id: str, solved_at: str, **extra: Any
) -> dict[str, Any]:
    body = {
        "platform": "codeforces",
        "external_id": ext_id,
        "title": f"Problem {ext_id}",
        "solved_at": solved_at,
        **extra,
    }
    res = client.post("/api/solves", headers=headers, json=body)
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


def test_empty_stats(client: TestClient, user_a: Headers, set_now: SetNow) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    assert client.get("/api/stats/summary", headers=user_a).json() == {
        "total": 0,
        "last_7_days": 0,
        "last_30_days": 0,
        "current_streak": 0,
        "longest_streak": 0,
    }
    heat = client.get("/api/stats/heatmap", headers=user_a).json()
    assert len(heat) == 365
    assert all(day["count"] == 0 for day in heat)
    assert heat[-1]["date"] == "2026-10-14"
    assert client.get("/api/stats/topics", headers=user_a).json() == []


def test_summary_and_streaks(client: TestClient, user_a: Headers, set_now: SetNow) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    add(client, user_a, "1A", "2026-10-14T08:00:00Z")
    add(client, user_a, "2A", "2026-10-13T08:00:00Z")
    add(client, user_a, "3A", "2026-10-13T09:00:00Z")
    add(client, user_a, "4A", "2026-10-01T09:00:00Z")
    add(client, user_a, "5A", "2026-09-01T09:00:00Z")
    summary = client.get("/api/stats/summary", headers=user_a).json()
    assert summary == {
        "total": 5,
        "last_7_days": 3,
        "last_30_days": 4,
        "current_streak": 2,
        "longest_streak": 2,
    }


def test_streak_survives_until_end_of_today(
    client: TestClient, user_a: Headers, set_now: SetNow
) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    add(client, user_a, "1A", "2026-10-13T08:00:00Z")
    add(client, user_a, "2A", "2026-10-12T08:00:00Z")
    assert client.get("/api/stats/summary", headers=user_a).json()["current_streak"] == 2
    set_now("2026-10-15T12:00:00+00:00")  # a day was skipped
    assert client.get("/api/stats/summary", headers=user_a).json()["current_streak"] == 0


def test_heatmap_uses_user_timezone_day_boundary(
    client: TestClient, user_a: Headers, set_now: SetNow
) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    # 22:30 UTC on Oct 10 is already Oct 11 in Moscow (UTC+3)
    add(client, user_a, "1A", "2026-10-10T22:30:00Z")
    params = {"from": "2026-10-09", "to": "2026-10-12"}
    heat = client.get("/api/stats/heatmap", headers=user_a, params=params).json()
    assert {d["date"]: d["count"] for d in heat} == {
        "2026-10-09": 0,
        "2026-10-10": 0,
        "2026-10-11": 1,
        "2026-10-12": 0,
    }
    client.patch("/api/me", headers=user_a, json={"timezone": "America/New_York"})
    heat = client.get("/api/stats/heatmap", headers=user_a, params=params).json()
    assert {d["date"]: d["count"] for d in heat}["2026-10-10"] == 1


def test_streak_crosses_month_boundary(
    client: TestClient, user_a: Headers, set_now: SetNow
) -> None:
    set_now("2026-03-01T12:00:00+00:00")
    add(client, user_a, "1A", "2026-02-27T12:00:00Z")
    add(client, user_a, "2A", "2026-02-28T12:00:00Z")
    add(client, user_a, "3A", "2026-03-01T09:00:00Z")
    summary = client.get("/api/stats/summary", headers=user_a).json()
    assert summary["current_streak"] == 3 and summary["longest_streak"] == 3


def test_heatmap_param_validation(client: TestClient, user_a: Headers) -> None:
    res = client.get(
        "/api/stats/heatmap", headers=user_a, params={"from": "2026-02-01", "to": "2026-01-01"}
    )
    assert res.status_code == 422
    res = client.get(
        "/api/stats/heatmap", headers=user_a, params={"from": "1990-01-01", "to": "2026-01-01"}
    )
    assert res.status_code == 422


def test_topics_with_review_quality(
    client: TestClient, user_a: Headers, set_now: SetNow, db: Session
) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    add(client, user_a, "1A", "2026-10-10T08:00:00Z", tags=["dp"], rating=1200)
    add(client, user_a, "2A", "2026-10-11T08:00:00Z", tags=["dp", "math"], rating=1400)
    add(client, user_a, "3A", "2026-10-12T08:00:00Z", tags=["math"])
    cards = db.scalars(select(ReviewCard).order_by(ReviewCard.id)).all()
    reviewed = datetime(2026, 10, 13, tzinfo=UTC)
    db.add_all(
        [
            ReviewLog(
                card_id=cards[0].id,
                reviewed_at=reviewed,
                quality=1,
                interval_after=1,
                ease_after=2.5,
            ),
            ReviewLog(
                card_id=cards[1].id,
                reviewed_at=reviewed,
                quality=5,
                interval_after=6,
                ease_after=2.6,
            ),
        ]
    )
    db.commit()

    topics = {t["tag"]: t for t in client.get("/api/stats/topics", headers=user_a).json()}
    assert topics["dp"]["solved"] == 2
    assert topics["dp"]["share"] == 2 / 3
    assert topics["dp"]["avg_rating"] == 1300
    assert topics["dp"]["avg_review_quality"] == 3.0
    assert topics["math"]["avg_rating"] == 1400
    assert topics["math"]["avg_review_quality"] == 5.0
    assert topics["math"]["last_solved_at"].startswith("2026-10-12")
    assert 0 <= topics["dp"]["weakness"] <= 1
    assert topics["dp"]["weakness"] > topics["math"]["weakness"]  # worse reviews


def test_stats_are_isolated_per_user(
    client: TestClient, user_a: Headers, user_b: Headers, set_now: SetNow
) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    add(client, user_a, "1A", "2026-10-14T08:00:00Z", tags=["dp"])
    assert client.get("/api/stats/summary", headers=user_b).json()["total"] == 0
    assert client.get("/api/stats/topics", headers=user_b).json() == []
    heat = client.get("/api/stats/heatmap", headers=user_b).json()
    assert sum(d["count"] for d in heat) == 0
