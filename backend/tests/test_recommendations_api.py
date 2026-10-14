from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AttemptStat, Platform, Problem, Tag
from scripts.eval_recommender import TAGS, make_synthetic_samples
from tests.conftest import CfMock

Headers = dict[str, str]
SetNow = Callable[[str], None]
NOW = "2026-10-14T12:00:00+00:00"


def big_problemset(count: int = 48) -> dict[str, Any]:
    problems, stats = [], []
    for i in range(count):
        contest = 3000 + i
        problems.append(
            {
                "contestId": contest,
                "index": "A",
                "name": f"Catalog problem {i}",
                "type": "PROGRAMMING",
                "rating": 800 + 100 * (i % 12),
                "tags": [TAGS[i % len(TAGS)], TAGS[(i + 3) % len(TAGS)]],
            }
        )
        stats.append({"contestId": contest, "index": "A", "solvedCount": 1000 * (i + 1)})
    return {"status": "OK", "result": {"problems": problems, "problemStatistics": stats}}


def test_new_user_gets_heuristic_recommendations(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow
) -> None:
    set_now(NOW)
    cf.responses["problemset.problems"] = big_problemset()
    res = client.get("/api/recommendations", headers=user_a)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["method"] == "heuristic"
    assert "Мало данных" in body["fallback_reason"]
    assert body["level"] == 800
    assert 0 < len(body["items"]) <= 5
    first = body["items"][0]
    assert first["predicted_solve_prob"] is None
    assert first["problem"]["url"].startswith("https://codeforces.com/problemset/problem/")
    assert all(700 <= i["problem"]["rating"] <= 1000 for i in body["items"])
    assert "Слабая тема" in first["reason"]


def test_limit_and_catalog_ttl(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow
) -> None:
    set_now(NOW)
    cf.responses["problemset.problems"] = big_problemset()
    assert (
        len(client.get("/api/recommendations", headers=user_a, params={"limit": 2}).json()["items"])
        == 2
    )
    client.get("/api/recommendations", headers=user_a)
    assert sum(r.url.path.endswith("problemset.problems") for r in cf.requests) == 1  # TTL 24h
    set_now("2026-10-16T12:00:00+00:00")
    client.get("/api/recommendations", headers=user_a)
    assert sum(r.url.path.endswith("problemset.problems") for r in cf.requests) == 2
    assert (
        client.get("/api/recommendations", headers=user_a, params={"limit": 0}).status_code == 422
    )


def test_solved_problems_are_not_recommended(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow
) -> None:
    set_now(NOW)
    cf.responses["problemset.problems"] = big_problemset()
    first = client.get("/api/recommendations", headers=user_a, params={"limit": 50}).json()["items"]
    target = first[0]["problem"]
    client.post(
        "/api/solves",
        headers=user_a,
        json={
            "platform": "codeforces",
            "external_id": target["external_id"],
            "title": target["title"],
            "rating": target["rating"],
            "tags": target["tags"],
        },
    )
    again = client.get("/api/recommendations", headers=user_a, params={"limit": 50}).json()["items"]
    assert target["external_id"] not in {i["problem"]["external_id"] for i in again}


def test_recommendations_are_per_user(
    client: TestClient, user_a: Headers, user_b: Headers, cf: CfMock, set_now: SetNow
) -> None:
    set_now(NOW)
    cf.responses["problemset.problems"] = big_problemset()
    for i in range(5):
        client.post(
            "/api/solves",
            headers=user_a,
            json={
                "platform": "codeforces",
                "external_id": f"1{i}A",
                "title": "t",
                "rating": 1600,
                "tags": ["dp"],
            },
        )
    assert client.get("/api/recommendations", headers=user_a).json()["level"] == 1600
    assert client.get("/api/recommendations", headers=user_b).json()["level"] == 800


def seed_attempts(db: Session, user_id: int, n: int, seed: int = 1) -> None:
    """Directly insert synthetic imported attempts for the ML branch."""
    tag_rows = {name: Tag(name=name) for name in TAGS}
    db.add_all(tag_rows.values())
    samples = make_synthetic_samples(n, seed)
    for i, s in enumerate(samples):
        problem = Problem(
            platform=Platform.codeforces,
            external_id=f"{500 + i}A",
            title=f"Attempted {i}",
            rating=s.rating,
            tags=[tag_rows[t] for t in s.tags],
        )
        db.add(problem)
        db.flush()
        db.add(
            AttemptStat(
                user_id=user_id,
                problem_id=problem.id,
                tries=1,
                solved=s.solved,
                first_attempt_at=s.first_attempt_at,
            )
        )
    db.commit()


def test_switches_to_ml_when_enough_attempts(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow, db: Session
) -> None:
    set_now(NOW)
    cf.responses["problemset.problems"] = big_problemset()
    user_id = client.get("/api/me", headers=user_a).json()["id"]
    seed_attempts(db, user_id, 300)
    # level estimate needs solves: add a few so candidates exist around a realistic level
    for i in range(6):
        client.post(
            "/api/solves",
            headers=user_a,
            json={
                "platform": "codeforces",
                "external_id": f"{9000 + i}A",
                "title": "s",
                "rating": 1200,
                "tags": ["dp"],
            },
        )
    res = client.get("/api/recommendations", headers=user_a, params={"limit": 4})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["method"] == "ml"
    assert body["fallback_reason"] is None
    assert len(body["items"]) == 4
    for item in body["items"]:
        assert 0 <= item["predicted_solve_prob"] <= 1
        assert "%" in item["reason"]


def test_ml_falls_back_when_classes_are_too_small(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow, db: Session
) -> None:
    set_now(NOW)
    cf.responses["problemset.problems"] = big_problemset()
    user_id = client.get("/api/me", headers=user_a).json()["id"]
    tag = Tag(name="dp")
    db.add(tag)
    base = datetime(2025, 1, 1, tzinfo=UTC)
    for i in range(120):
        problem = Problem(
            platform=Platform.codeforces,
            external_id=f"{700 + i}A",
            title="x",
            rating=1000,
            tags=[tag],
        )
        db.add(problem)
        db.flush()
        db.add(
            AttemptStat(
                user_id=user_id,
                problem_id=problem.id,
                tries=1,
                solved=i < 5,
                first_attempt_at=base + timedelta(hours=i),
            )
        )
    db.commit()
    body = client.get("/api/recommendations", headers=user_a).json()
    assert body["method"] == "heuristic"
    assert "решённых 5" in body["fallback_reason"]


def test_catalog_failure_without_cache_is_502(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow
) -> None:
    set_now(NOW)
    cf.responses["problemset.problems"] = lambda request: httpx.Response(503)
    assert client.get("/api/recommendations", headers=user_a).status_code == 502


def test_requires_auth(client: TestClient, cf: CfMock) -> None:
    assert client.get("/api/recommendations").status_code == 401
