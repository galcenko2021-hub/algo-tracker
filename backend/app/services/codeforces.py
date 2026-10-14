"""Client for the public Codeforces API (https://codeforces.com/apiHelp).

Only the documented public endpoints are used: `user.status` and `problemset.problems`.
The client throttles requests (Codeforces allows at most one request per two seconds),
applies timeouts and retries transient failures with exponential backoff.
"""

import threading
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 30.0
MAX_RETRIES = 2
BACKOFF_BASE_SECONDS = 1.0
GYM_CONTEST_ID_FROM = 100_000


class CodeforcesError(Exception):
    """Base class for Codeforces failures."""


class CodeforcesNotFound(CodeforcesError):
    """Unknown (or invalid) handle."""


class CodeforcesUnavailable(CodeforcesError):
    """Network problem, 5xx, malformed answer or any other API failure."""


class CodeforcesRateLimited(CodeforcesError):
    """Codeforces refused the request because of its call limit."""


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


# Field names mirror the Codeforces JSON, hence camelCase.
class CfProblem(_Lenient):
    contestId: int | None = None
    index: str
    name: str
    rating: int | None = None
    tags: list[str] = Field(default_factory=list)


class CfSubmission(_Lenient):
    id: int
    contestId: int | None = None
    creationTimeSeconds: int
    problem: CfProblem
    verdict: str | None = None


class CfProblemStatistic(_Lenient):
    contestId: int | None = None
    index: str
    solvedCount: int = 0


class CfProblemset(_Lenient):
    problems: list[CfProblem]
    problemStatistics: list[CfProblemStatistic] = Field(default_factory=list)


class Throttle:
    """Process-wide limiter: at least `interval` seconds between two calls to `wait()`."""

    def __init__(
        self,
        interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last: float | None = None

    def wait(self) -> None:
        with self._lock:
            if self._last is not None:
                delay = self._last + self._interval - self._clock()
                if delay > 0:
                    self._sleep(delay)
            self._last = self._clock()


class CodeforcesClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        throttle: Throttle | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.cf_base_url).rstrip("/")
        self._throttle = throttle or Throttle(settings.cf_min_interval_seconds)
        self._transport = transport
        self._sleep = sleep

    def _request_once(self, path: str, params: dict[str, str]) -> Any:
        self._throttle.wait()
        timeout = httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)
        try:
            with httpx.Client(timeout=timeout, transport=self._transport) as http:
                response = http.get(f"{self._base_url}/{path}", params=params)
        except httpx.HTTPError as exc:
            raise CodeforcesUnavailable(f"Codeforces недоступен: {type(exc).__name__}") from exc

        if response.status_code == 429:
            raise CodeforcesRateLimited("Codeforces ограничил число запросов")
        if response.status_code >= 500:
            raise CodeforcesUnavailable(f"Codeforces вернул HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise CodeforcesUnavailable("Codeforces вернул не-JSON ответ") from exc
        if not isinstance(payload, dict):
            raise CodeforcesUnavailable("Неожиданный формат ответа Codeforces")

        if payload.get("status") != "OK":
            comment = str(payload.get("comment", ""))
            lowered = comment.lower()
            if "limit exceeded" in lowered:
                raise CodeforcesRateLimited("Codeforces ограничил число запросов")
            if lowered.startswith("handle:"):
                raise CodeforcesNotFound(comment)
            raise CodeforcesUnavailable(f"Codeforces отклонил запрос: {comment or 'FAILED'}")
        return payload.get("result")

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        params = params or {}
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self._request_once(path, params)
            except (CodeforcesUnavailable, CodeforcesRateLimited):
                if attempt == MAX_RETRIES:
                    raise
                self._sleep(BACKOFF_BASE_SECONDS * 2**attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    def user_status(self, handle: str) -> list[CfSubmission]:
        result = self._get("user.status", {"handle": handle})
        try:
            return [CfSubmission.model_validate(item) for item in result]
        except (ValidationError, TypeError) as exc:
            raise CodeforcesUnavailable("Неожиданный формат посылок Codeforces") from exc

    def problemset(self) -> CfProblemset:
        result = self._get("problemset.problems")
        try:
            return CfProblemset.model_validate(result)
        except ValidationError as exc:
            raise CodeforcesUnavailable("Неожиданный формат списка задач Codeforces") from exc


_shared_throttle: Throttle | None = None


def get_codeforces_client() -> CodeforcesClient:
    """FastAPI dependency. The throttle is shared so concurrent requests respect the limit."""
    global _shared_throttle
    if _shared_throttle is None:
        _shared_throttle = Throttle(get_settings().cf_min_interval_seconds)
    return CodeforcesClient(throttle=_shared_throttle)
