from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ReviewCard, ReviewLog

Headers = dict[str, str]
SetNow = Callable[[str], None]


def add(client: TestClient, headers: Headers, ext_id: str, solved_at: str, **extra: Any) -> None:
    body = {
        "platform": "codeforces",
        "external_id": ext_id,
        "title": f"Problem {ext_id}",
        "solved_at": solved_at,
        "notes": f"note {ext_id}",
        **extra,
    }
    assert client.post("/api/solves", headers=headers, json=body).status_code == 201


def test_new_solve_is_due_next_day_not_today(
    client: TestClient, user_a: Headers, set_now: SetNow
) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    add(client, user_a, "1A", "2026-10-14T08:00:00Z")
    assert client.get("/api/reviews/due", headers=user_a).json() == {"count": 0, "cards": []}
    set_now("2026-10-15T12:00:00+00:00")
    due = client.get("/api/reviews/due", headers=user_a).json()
    assert due["count"] == 1
    card = due["cards"][0]
    assert card["problem"]["external_id"] == "1A"
    assert card["notes"] == "note 1A"
    assert card["next_intervals"] == {"again": 1, "hard": 1, "good": 1, "easy": 1}


def test_due_includes_overdue_ordered_oldest_first(
    client: TestClient, user_a: Headers, set_now: SetNow
) -> None:
    set_now("2026-10-12T12:00:00+00:00")
    add(client, user_a, "LATE", "2026-10-12T08:00:00Z")  # due Oct 13
    set_now("2026-10-10T12:00:00+00:00")
    add(client, user_a, "EARLY", "2026-10-10T08:00:00Z")  # due Oct 11
    set_now("2026-10-20T12:00:00+00:00")
    due = client.get("/api/reviews/due", headers=user_a).json()
    assert due["count"] == 2
    assert [c["problem"]["external_id"] for c in due["cards"]] == ["EARLY", "LATE"]


def test_backdated_solve_is_due_today_not_overdue(
    client: TestClient, user_a: Headers, set_now: SetNow
) -> None:
    set_now("2026-10-20T12:00:00+00:00")
    add(client, user_a, "OLD", "2026-09-01T08:00:00Z")
    assert client.get("/api/reviews/due", headers=user_a).json()["count"] == 1


def test_answer_applies_sm2_and_writes_log(
    client: TestClient, user_a: Headers, set_now: SetNow, db: Session
) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    add(client, user_a, "1A", "2026-10-13T08:00:00Z")
    card_id = client.get("/api/reviews/due", headers=user_a).json()["cards"][0]["card_id"]

    res = client.post(f"/api/reviews/{card_id}/answer", headers=user_a, json={"quality": 4})
    assert res.status_code == 200
    assert res.json() == {
        "card_id": card_id,
        "interval_days": 1,
        "due_date": "2026-10-15",
        "ease": 2.5,
        "repetitions": 1,
        "lapses": 0,
    }
    assert client.get("/api/reviews/due", headers=user_a).json()["count"] == 0

    set_now("2026-10-15T12:00:00+00:00")
    res = client.post(f"/api/reviews/{card_id}/answer", headers=user_a, json={"quality": 5})
    assert (res.json()["interval_days"], res.json()["due_date"]) == (6, "2026-10-21")
    assert res.json()["ease"] == 2.6

    set_now("2026-10-21T12:00:00+00:00")
    res = client.post(f"/api/reviews/{card_id}/answer", headers=user_a, json={"quality": 1})
    assert res.json()["interval_days"] == 1 and res.json()["lapses"] == 1
    assert res.json()["repetitions"] == 0

    logs = db.scalars(select(ReviewLog).order_by(ReviewLog.id)).all()
    assert [log.quality for log in logs] == [4, 5, 1]
    assert [log.interval_after for log in logs] == [1, 6, 1]
    card = db.scalars(select(ReviewCard)).one()
    assert card.last_reviewed_at is not None


def test_answer_validation_and_missing_card(client: TestClient, user_a: Headers) -> None:
    assert (
        client.post("/api/reviews/999/answer", headers=user_a, json={"quality": 4}).status_code
        == 404
    )
    assert (
        client.post("/api/reviews/1/answer", headers=user_a, json={"quality": 6}).status_code == 422
    )
    assert (
        client.post("/api/reviews/1/answer", headers=user_a, json={"quality": -1}).status_code
        == 422
    )
    assert client.post("/api/reviews/1/answer", headers=user_a, json={}).status_code == 422


def test_cannot_answer_other_users_card(
    client: TestClient, user_a: Headers, user_b: Headers, set_now: SetNow
) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    add(client, user_a, "1A", "2026-10-10T08:00:00Z")
    card_id = client.get("/api/reviews/due", headers=user_a).json()["cards"][0]["card_id"]
    res = client.post(f"/api/reviews/{card_id}/answer", headers=user_b, json={"quality": 4})
    assert res.status_code == 404
    assert client.get("/api/reviews/due", headers=user_b).json() == {"count": 0, "cards": []}
    assert client.get("/api/reviews/upcoming", headers=user_b).json()[0]["count"] == 0
    # untouched for the owner
    assert client.get("/api/reviews/due", headers=user_a).json()["count"] == 1


def test_due_limit_keeps_full_count(client: TestClient, user_a: Headers, set_now: SetNow) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    for i in range(3):
        add(client, user_a, f"{i}A", "2026-10-01T08:00:00Z")
    res = client.get("/api/reviews/due", headers=user_a, params={"limit": 2}).json()
    assert res["count"] == 3 and len(res["cards"]) == 2


def test_upcoming_counts_per_day_with_overdue_on_today(
    client: TestClient, user_a: Headers, set_now: SetNow
) -> None:
    set_now("2026-10-14T12:00:00+00:00")
    add(client, user_a, "OLD", "2026-10-01T08:00:00Z")  # due today
    add(client, user_a, "1A", "2026-10-14T08:00:00Z")  # due Oct 15
    add(client, user_a, "2A", "2026-10-14T09:00:00Z")  # due Oct 15
    cid = client.get("/api/reviews/due", headers=user_a).json()["cards"][0]["card_id"]
    client.post(f"/api/reviews/{cid}/answer", headers=user_a, json={"quality": 5})  # -> Oct 15

    up = client.get("/api/reviews/upcoming", headers=user_a, params={"days": 3}).json()
    assert up == [
        {"date": "2026-10-14", "count": 0},
        {"date": "2026-10-15", "count": 3},
        {"date": "2026-10-16", "count": 0},
    ]
    assert len(client.get("/api/reviews/upcoming", headers=user_a).json()) == 14
    assert (
        client.get("/api/reviews/upcoming", headers=user_a, params={"days": 0}).status_code == 422
    )
    assert (
        client.get("/api/reviews/upcoming", headers=user_a, params={"days": 91}).status_code == 422
    )
