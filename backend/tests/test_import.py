from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AttemptStat, Problem, ReviewCard, Solve, SolveSource
from app.services.codeforces import CfSubmission, CodeforcesClient, Throttle
from app.services.importer import aggregate_submissions, assign_due_dates
from tests.conftest import CfMock, load_fixture

Headers = dict[str, str]
SetNow = Callable[[str], None]
NOW = "2026-10-14T12:00:00+00:00"


def submissions() -> list[CfSubmission]:
    return [CfSubmission.model_validate(s) for s in load_fixture("cf_user_status.json")["result"]]


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


# ---------- pure aggregation ----------


def test_aggregate_collapses_submissions_per_problem() -> None:
    agg = aggregate_submissions(submissions())
    assert set(agg) == {"1700A", "1700B", "1701C", "1800D"}  # gym 100500 skipped

    a = agg["1700A"]
    assert (a.tries, a.solved) == (3, True)
    assert a.first_ok_at == datetime.fromtimestamp(
        1700000100, tz=UTC
    )  # first OK, not the later one
    assert a.first_attempt_at == datetime.fromtimestamp(1700000050, tz=UTC)
    assert a.tags == ["greedy", "math"]
    assert a.url == "https://codeforces.com/problemset/problem/1700/A"

    b = agg["1700B"]
    assert (b.tries, b.solved, b.first_ok_at) == (2, False, None)
    assert agg["1800D"].tries == 3 and agg["1800D"].solved
    assert agg["1701C"].rating is None


def test_aggregate_skips_submissions_without_contest() -> None:
    raw = {
        "id": 1,
        "creationTimeSeconds": 1,
        "problem": {"index": "A", "name": "x", "tags": []},
        "verdict": "OK",
    }
    assert aggregate_submissions([CfSubmission.model_validate(raw)]) == {}


# ---------- due date spreading ----------


def test_assign_due_dates_caps_new_cards_per_day() -> None:
    today = date(2026, 10, 14)
    dues = assign_due_dates([today] * 25)
    assert Counter(dues) == {today: 10, today + timedelta(days=1): 10, today + timedelta(days=2): 5}


def test_assign_due_dates_respects_earliest_and_occupied() -> None:
    today = date(2026, 10, 14)
    tomorrow = today + timedelta(days=1)
    dues = assign_due_dates([tomorrow, today, today], occupied={today: 9})
    assert dues == [tomorrow, today, tomorrow]
    assert assign_due_dates([]) == []


# ---------- throttle, retries, errors ----------


def test_throttle_enforces_minimum_interval() -> None:
    clock = [100.0]
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        clock[0] += seconds

    throttle = Throttle(2.0, clock=lambda: clock[0], sleep=sleep)
    throttle.wait()  # first call never waits
    clock[0] += 0.5
    throttle.wait()
    clock[0] += 5
    throttle.wait()  # enough time has passed
    assert slept == [pytest.approx(1.5)]


def test_client_retries_transient_failures_with_exponential_backoff(cf: CfMock) -> None:
    ok = cf.responses["user.status"]
    calls = [httpx.Response(500), httpx.Response(503), httpx.Response(200, json=ok)]
    cf.responses["user.status"] = lambda request: calls.pop(0)
    assert len(cf.client().user_status("tourist")) == 10
    assert len(cf.requests) == 3
    assert cf.sleeps == [1.0, 2.0]


def test_client_gives_up_after_two_retries(cf: CfMock) -> None:
    cf.responses["user.status"] = lambda request: httpx.Response(500)
    client = cf.client()
    with pytest.raises(Exception, match="HTTP 500"):
        client.user_status("tourist")
    assert len(cf.requests) == 3


def test_client_sends_expected_request(cf: CfMock) -> None:
    cf.client().user_status("tourist")
    request = cf.requests[0]
    assert request.url.path == "/api/user.status"
    assert dict(request.url.params) == {"handle": "tourist"}


def test_client_rejects_malformed_payload(cf: CfMock) -> None:
    cf.responses["user.status"] = {"status": "OK", "result": [{"id": "not-a-submission"}]}
    with pytest.raises(Exception, match="формат"):
        cf.client().user_status("tourist")
    assert isinstance(cf.client(), CodeforcesClient)


# ---------- API: happy path and idempotency ----------


def test_import_creates_solves_attempts_and_cards(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow, db: Session
) -> None:
    set_now(NOW)
    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert res.status_code == 200, res.text
    assert res.json() == {"imported": 3, "skipped": 0, "attempts_recorded": 4}

    solves = {s.problem.external_id: s for s in db.scalars(select(Solve)).unique()}
    assert set(solves) == {"1700A", "1701C", "1800D"}  # 1700B was never accepted
    assert all(s.source is SolveSource.codeforces for s in solves.values())
    assert solves["1700A"].solved_at == datetime.fromtimestamp(1700000100, tz=UTC)

    attempts = {
        a.problem_id: a for a in db.scalars(select(AttemptStat).where(AttemptStat.user_id == 1))
    }
    by_ext = {
        p.external_id: attempts[p.id] for p in db.scalars(select(Problem)) if p.id in attempts
    }
    assert (by_ext["1700B"].tries, by_ext["1700B"].solved) == (2, False)
    assert (by_ext["1800D"].tries, by_ext["1800D"].solved) == (3, True)

    problem = db.scalars(select(Problem).where(Problem.external_id == "1800D")).one()
    assert [t.name for t in problem.tags] == ["data structures", "strings"]
    assert problem.rating == 1300

    cards = db.scalars(select(ReviewCard)).all()
    assert len(cards) == 3
    assert all(c.due_date >= date(2026, 10, 14) for c in cards)  # no overdue avalanche

    listing = client.get("/api/solves", headers=user_a).json()
    assert listing["total"] == 3


def test_import_is_idempotent(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow, db: Session
) -> None:
    set_now(NOW)
    first = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    snapshot = (
        count(db, Solve),
        count(db, Problem),
        count(db, AttemptStat),
        count(db, ReviewCard),
    )
    second = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert first.json()["imported"] == 3
    assert second.json() == {"imported": 0, "skipped": 3, "attempts_recorded": 0}
    assert (
        count(db, Solve),
        count(db, Problem),
        count(db, AttemptStat),
        count(db, ReviewCard),
    ) == snapshot


def test_import_updates_attempt_stats_when_new_submissions_arrive(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow, db: Session
) -> None:
    set_now(NOW)
    client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    payload = load_fixture("cf_user_status.json")
    extra = dict(payload["result"][0])  # accepted gym -> use a 1700B OK submission instead
    extra.update(id=100, verdict="OK", creationTimeSeconds=1700900000)
    extra["problem"] = next(s["problem"] for s in payload["result"] if s["problem"]["index"] == "B")
    extra["contestId"] = 1700
    payload["result"].append(extra)
    cf.responses["user.status"] = payload

    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert res.json() == {"imported": 1, "skipped": 3, "attempts_recorded": 1}
    assert count(db, Solve) == 4
    assert count(db, AttemptStat) == 4


def test_manual_solve_is_skipped_not_duplicated_or_overwritten(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow, db: Session
) -> None:
    set_now(NOW)
    manual = {
        "platform": "codeforces",
        "external_id": "1700A",
        "title": "Optimal Path",
        "solved_at": "2026-01-05T10:00:00Z",
        "notes": "my own note",
    }
    assert client.post("/api/solves", headers=user_a, json=manual).status_code == 201
    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert res.json() == {"imported": 2, "skipped": 1, "attempts_recorded": 4}
    solve = next(s for s in db.scalars(select(Solve)).unique() if s.problem.external_id == "1700A")
    assert solve.source is SolveSource.manual
    assert solve.notes == "my own note"
    assert count(db, Solve) == 3


def test_import_spreads_first_reviews(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow, db: Session
) -> None:
    set_now(NOW)
    base = load_fixture("cf_user_status.json")["result"][1]  # a 1800D template
    many = []
    for i in range(25):
        sub = dict(base)
        sub["id"] = 1000 + i
        sub["creationTimeSeconds"] = 1600000000 + i
        sub["problem"] = {**base["problem"], "contestId": 2000 + i, "index": "A"}
        sub["contestId"] = 2000 + i
        many.append(sub)
    cf.responses["user.status"] = {"status": "OK", "result": many}
    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert res.json()["imported"] == 25
    per_day = Counter(c.due_date for c in db.scalars(select(ReviewCard)))
    assert max(per_day.values()) == 10
    assert min(per_day) == date(2026, 10, 14)
    assert len(per_day) == 3


def test_import_uses_profile_handle_and_validates(
    client: TestClient, user_a: Headers, cf: CfMock, set_now: SetNow
) -> None:
    set_now(NOW)
    no_handle = client.post("/api/import/codeforces", headers=user_a)
    assert no_handle.status_code == 422
    client.patch("/api/me", headers=user_a, json={"cf_handle": "tourist"})
    assert client.post("/api/import/codeforces", headers=user_a).status_code == 200
    assert dict(cf.requests[-1].url.params) == {"handle": "tourist"}
    bad = client.post("/api/import/codeforces", headers=user_a, json={"handle": "a b/c"})
    assert bad.status_code == 422


def test_import_data_is_isolated_between_users(
    client: TestClient, user_a: Headers, user_b: Headers, cf: CfMock, set_now: SetNow
) -> None:
    set_now(NOW)
    client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert client.get("/api/solves", headers=user_b).json()["total"] == 0
    res = client.post("/api/import/codeforces", headers=user_b, json={"handle": "tourist"})
    assert res.json()["imported"] == 3  # problems are shared, solves are not
    assert client.get("/api/solves", headers=user_a).json()["total"] == 3


def test_import_requires_auth(client: TestClient, cf: CfMock) -> None:
    assert client.post("/api/import/codeforces", json={"handle": "x"}).status_code == 401


# ---------- API: Codeforces failures ----------


def test_unknown_handle_is_404(client: TestClient, user_a: Headers, cf: CfMock) -> None:
    cf.responses["user.status"] = lambda request: httpx.Response(
        400, json=load_fixture("cf_user_not_found.json")
    )
    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "ghost_user"})
    assert res.status_code == 404
    assert "ghost_user" in res.json()["detail"]
    assert len(cf.requests) == 1  # not retried


def test_codeforces_down_is_502(client: TestClient, user_a: Headers, cf: CfMock) -> None:
    cf.responses["user.status"] = lambda request: httpx.Response(503)
    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert res.status_code == 502
    assert len(cf.requests) == 3


def test_network_error_is_502(client: TestClient, user_a: Headers, cf: CfMock) -> None:
    cf.responses["user.status"] = httpx.ConnectTimeout("boom")
    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert res.status_code == 502


def test_non_json_answer_is_502(client: TestClient, user_a: Headers, cf: CfMock) -> None:
    cf.responses["user.status"] = lambda request: httpx.Response(200, text="<html>maintenance")
    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert res.status_code == 502


def test_rate_limited_by_codeforces_is_429(client: TestClient, user_a: Headers, cf: CfMock) -> None:
    cf.responses["user.status"] = lambda request: httpx.Response(
        200, json={"status": "FAILED", "comment": "Call limit exceeded"}
    )
    res = client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert res.status_code == 429


def test_failed_import_leaves_no_partial_data(
    client: TestClient, user_a: Headers, cf: CfMock, db: Session
) -> None:
    cf.responses["user.status"] = lambda request: httpx.Response(503)
    client.post("/api/import/codeforces", headers=user_a, json={"handle": "tourist"})
    assert count(db, Solve) == 0 and count(db, Problem) == 0 and count(db, AttemptStat) == 0
