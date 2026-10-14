from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ReviewCard, ReviewLog
from app.services.solves import (
    codeforces_url,
    first_review_date,
    generate_external_id,
)

Headers = dict[str, str]


def solve_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "platform": "codeforces",
        "external_id": "1700A",
        "title": "Optimal Path",
        "rating": 800,
        "tags": ["Math", "greedy"],
    }
    body.update(overrides)
    return body


def add(client: TestClient, headers: Headers, **overrides: Any) -> dict[str, Any]:
    res = client.post("/api/solves", headers=headers, json=solve_body(**overrides))
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


def test_create_solve_builds_problem_tags_and_card(
    client: TestClient, user_a: Headers, db: Session
) -> None:
    solved_at = datetime.now(UTC)
    data = add(client, user_a, solved_at=solved_at.isoformat())
    assert data["source"] == "manual"
    assert data["problem"]["external_id"] == "1700A"
    assert data["problem"]["tags"] == ["greedy", "math"]  # lowercased + sorted
    assert data["problem"]["url"] == "https://codeforces.com/problemset/problem/1700/A"

    card = db.scalars(select(ReviewCard)).one()
    assert card.ease == 2.5 and card.repetitions == 0
    assert card.due_date >= date.today()  # never in the past
    assert card.due_date - date.today() <= timedelta(days=2)


def test_card_due_next_local_day_for_recent_solve() -> None:
    assert first_review_date(date(2026, 10, 12), date(2026, 10, 12)) == date(2026, 10, 13)
    assert first_review_date(date(2026, 1, 1), date(2026, 10, 12)) == date(2026, 10, 12)


def test_duplicate_solve_is_409(client: TestClient, user_a: Headers) -> None:
    add(client, user_a)
    res = client.post("/api/solves", headers=user_a, json=solve_body())
    assert res.status_code == 409


def test_other_platform_without_external_id_gets_stable_id(
    client: TestClient, user_a: Headers
) -> None:
    first = add(client, user_a, platform="other", external_id=None, title="  My   Problem ")
    assert first["problem"]["external_id"] == generate_external_id("my problem")
    dup = client.post(
        "/api/solves",
        headers=user_a,
        json=solve_body(platform="other", external_id=None, title="my problem"),
    )
    assert dup.status_code == 409


def test_codeforces_url_helper() -> None:
    assert codeforces_url("1700a") == "https://codeforces.com/problemset/problem/1700/A"
    assert codeforces_url("1700B2") == "https://codeforces.com/problemset/problem/1700/B2"
    assert codeforces_url("nonsense") is None


def test_validation_errors(client: TestClient, user_a: Headers) -> None:
    for bad in (
        {"title": ""},
        {"notes": "x" * 2001},
        {"url": "javascript:alert(1)"},
        {"rating": -5},
        {"platform": "topcoder"},
        {"solved_at": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
    ):
        res = client.post("/api/solves", headers=user_a, json=solve_body(**bad))
        assert res.status_code == 422, bad


def test_requires_auth(client: TestClient) -> None:
    assert client.get("/api/solves").status_code == 401
    assert client.post("/api/solves", json=solve_body()).status_code == 401
    assert client.get("/api/tags").status_code == 401


def seed(client: TestClient, headers: Headers) -> None:
    add(
        client,
        headers,
        external_id="1A",
        title="Watermelon",
        platform="codeforces",
        tags=["math"],
        solved_at="2026-03-01T12:00:00Z",
    )
    add(
        client,
        headers,
        external_id="2B",
        title="Knapsack Basics",
        platform="leetcode",
        tags=["dp", "math"],
        solved_at="2026-03-10T12:00:00Z",
    )
    add(
        client,
        headers,
        external_id="3C",
        title="Graph 100%",
        platform="yandex",
        tags=["graphs"],
        solved_at="2026-03-20T12:00:00Z",
    )


def test_list_sorted_desc_and_paginated(client: TestClient, user_a: Headers) -> None:
    seed(client, user_a)
    page1 = client.get("/api/solves", headers=user_a, params={"page_size": 2}).json()
    assert page1["total"] == 3
    assert [s["problem"]["external_id"] for s in page1["items"]] == ["3C", "2B"]
    page2 = client.get("/api/solves", headers=user_a, params={"page_size": 2, "page": 2}).json()
    assert [s["problem"]["external_id"] for s in page2["items"]] == ["1A"]
    assert client.get("/api/solves", headers=user_a, params={"page_size": 101}).status_code == 422
    assert client.get("/api/solves", headers=user_a, params={"page": 0}).status_code == 422


def test_list_filters(client: TestClient, user_a: Headers) -> None:
    seed(client, user_a)

    def ids(**params: Any) -> list[str]:
        res = client.get("/api/solves", headers=user_a, params=params).json()
        return [s["problem"]["external_id"] for s in res["items"]]

    assert ids(tag="math") == ["2B", "1A"]
    assert ids(tag=["math", "dp"]) == ["2B"]  # AND semantics
    assert ids(platform="yandex") == ["3C"]
    assert ids(q="knap") == ["2B"]
    assert ids(q="3c") == ["3C"]  # also matches external id
    assert ids(q="100%") == ["3C"]  # LIKE wildcards are escaped
    assert ids(q="%") == ["3C"]
    assert ids(**{"from": "2026-03-10", "to": "2026-03-10"}) == ["2B"]
    assert ids(**{"from": "2026-03-11"}) == ["3C"]
    assert ids(**{"to": "2026-03-09"}) == ["1A"]


def test_date_filter_uses_user_timezone(client: TestClient, user_a: Headers) -> None:
    client.patch("/api/me", headers=user_a, json={"timezone": "Asia/Tokyo"})  # UTC+9
    add(client, user_a, solved_at="2026-03-01T20:00:00Z")  # 05:00 on Mar 2 in Tokyo
    on_day = client.get(
        "/api/solves", headers=user_a, params={"from": "2026-03-02", "to": "2026-03-02"}
    )
    assert on_day.json()["total"] == 1
    before = client.get("/api/solves", headers=user_a, params={"to": "2026-03-01"})
    assert before.json()["total"] == 0


def test_patch_solve_level_fields(client: TestClient, user_a: Headers) -> None:
    sid = add(client, user_a)["id"]
    res = client.patch(
        f"/api/solves/{sid}",
        headers=user_a,
        json={"notes": "use a heap", "time_spent_min": 25, "solved_at": "2026-02-01T10:00:00Z"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["notes"] == "use a heap" and body["time_spent_min"] == 25
    assert body["solved_at"].startswith("2026-02-01")
    cleared = client.patch(f"/api/solves/{sid}", headers=user_a, json={"notes": None}).json()
    assert cleared["notes"] is None and cleared["time_spent_min"] == 25


def test_patch_private_problem_metadata(client: TestClient, user_a: Headers) -> None:
    sid = add(client, user_a)["id"]
    res = client.patch(
        f"/api/solves/{sid}", headers=user_a, json={"title": "New", "rating": 900, "tags": ["dp"]}
    )
    assert res.status_code == 200
    problem = res.json()["problem"]
    assert (problem["title"], problem["rating"], problem["tags"]) == ("New", 900, ["dp"])


def test_patch_shared_problem_metadata_is_forbidden(
    client: TestClient, user_a: Headers, user_b: Headers
) -> None:
    sid_a = add(client, user_a)["id"]
    add(client, user_b, title="Different title is ignored for shared problem")
    res = client.patch(f"/api/solves/{sid_a}", headers=user_a, json={"title": "Hijack"})
    assert res.status_code == 403
    same = client.patch(f"/api/solves/{sid_a}", headers=user_a, json={"notes": "fine"})
    assert same.status_code == 200
    assert same.json()["problem"]["title"] == "Optimal Path"


def test_delete_solve_removes_card_and_log(
    client: TestClient, user_a: Headers, db: Session
) -> None:
    sid = add(client, user_a)["id"]
    card = db.scalars(select(ReviewCard)).one()
    db.add(
        ReviewLog(
            card_id=card.id,
            reviewed_at=datetime.now(UTC),
            quality=4,
            interval_after=1,
            ease_after=2.5,
        )
    )
    db.commit()
    assert client.delete(f"/api/solves/{sid}", headers=user_a).status_code == 204
    assert db.scalar(select(func.count()).select_from(ReviewCard)) == 0
    assert db.scalar(select(func.count()).select_from(ReviewLog)) == 0
    assert client.delete(f"/api/solves/{sid}", headers=user_a).status_code == 404
    # can be added again after deletion
    add(client, user_a)


def test_data_isolation_between_users(
    client: TestClient, user_a: Headers, user_b: Headers, db: Session
) -> None:
    sid = add(client, user_a, tags=["secret-tag"])["id"]

    assert client.get("/api/solves", headers=user_b).json()["total"] == 0
    assert client.get("/api/tags", headers=user_b).json() == []
    assert (
        client.patch(f"/api/solves/{sid}", headers=user_b, json={"notes": "x"}).status_code == 404
    )
    assert client.delete(f"/api/solves/{sid}", headers=user_b).status_code == 404

    # still intact for the owner, including the review card
    assert client.get("/api/solves", headers=user_a).json()["total"] == 1
    assert db.scalar(select(func.count()).select_from(ReviewCard)) == 1

    # user B can add the same (shared) problem independently
    add(client, user_b)
    assert client.get("/api/solves", headers=user_b).json()["total"] == 1
    assert client.get("/api/solves", headers=user_a).json()["total"] == 1


def test_tag_autocomplete_is_per_user(client: TestClient, user_a: Headers, user_b: Headers) -> None:
    seed(client, user_a)
    add(client, user_b, external_id="9Z", title="B only", tags=["secret"])
    assert client.get("/api/tags", headers=user_a).json() == ["math", "dp", "graphs"]
    assert client.get("/api/tags", headers=user_a, params={"q": "GR"}).json() == ["graphs"]
    assert client.get("/api/tags", headers=user_b).json() == ["secret"]
