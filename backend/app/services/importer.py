"""Import of a user's Codeforces submissions: aggregation, deduplication and bulk insertion."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

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
from app.services.codeforces import GYM_CONTEST_ID_FROM, CfSubmission
from app.services.solves import first_review_date

MAX_NEW_CARDS_PER_DAY = 10


@dataclass
class ProblemAggregate:
    external_id: str
    title: str
    rating: int | None
    tags: list[str]
    tries: int = 0
    first_attempt_at: datetime | None = None
    first_ok_at: datetime | None = None
    url: str = field(default="", init=False)

    def __post_init__(self) -> None:
        contest, index = _split_external_id(self.external_id)
        self.url = f"https://codeforces.com/problemset/problem/{contest}/{index}"

    @property
    def solved(self) -> bool:
        return self.first_ok_at is not None


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int
    attempts_recorded: int


def _split_external_id(external_id: str) -> tuple[str, str]:
    digits = len(external_id) - len(external_id.lstrip("0123456789"))
    return external_id[:digits], external_id[digits:]


def aggregate_submissions(submissions: Iterable[CfSubmission]) -> dict[str, ProblemAggregate]:
    """Collapse submissions into one record per problem. Gym contests are skipped."""
    result: dict[str, ProblemAggregate] = {}
    for sub in submissions:
        contest_id = sub.problem.contestId if sub.problem.contestId is not None else sub.contestId
        if contest_id is None or contest_id >= GYM_CONTEST_ID_FROM:
            continue
        external_id = f"{contest_id}{sub.problem.index}"
        agg = result.get(external_id)
        if agg is None:
            agg = result[external_id] = ProblemAggregate(
                external_id=external_id,
                title=sub.problem.name,
                rating=sub.problem.rating,
                tags=sorted({t.strip().lower() for t in sub.problem.tags if t.strip()}),
            )
        moment = datetime.fromtimestamp(sub.creationTimeSeconds, tz=UTC)
        agg.tries += 1
        if agg.first_attempt_at is None or moment < agg.first_attempt_at:
            agg.first_attempt_at = moment
        if sub.verdict == "OK" and (agg.first_ok_at is None or moment < agg.first_ok_at):
            agg.first_ok_at = moment
    return result


def assign_due_dates(
    earliest: Sequence[date],
    occupied: dict[date, int] | None = None,
    per_day: int = MAX_NEW_CARDS_PER_DAY,
) -> list[date]:
    """Spread first reviews: each card gets the first day >= its earliest date with free capacity.

    `occupied` holds how many new cards already sit on a given day. Cards are served in order
    of their earliest date, so the oldest solves are reviewed first. The result is returned in
    the same order as `earliest`.
    """
    load: dict[date, int] = defaultdict(int, occupied or {})
    result: list[date | None] = [None] * len(earliest)
    for position in sorted(range(len(earliest)), key=lambda i: (earliest[i], i)):
        day = earliest[position]
        while load[day] >= per_day:
            day += timedelta(days=1)
        load[day] += 1
        result[position] = day
    return [d for d in result if d is not None]


def _chunks[T](items: Sequence[T], size: int = 2000) -> Iterable[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def import_submissions(
    db: Session, user: User, submissions: Iterable[CfSubmission], now: datetime
) -> ImportResult:
    """Idempotent import in one transaction (the caller's); rows are inserted in bulk."""
    aggregates = aggregate_submissions(submissions)
    if not aggregates:
        return ImportResult(imported=0, skipped=0, attempts_recorded=0)

    problem_ids = _ensure_problems(db, aggregates)
    attempts_recorded = _upsert_attempts(db, user, aggregates, problem_ids)

    existing_solved = set(db.scalars(select(Solve.problem_id).where(Solve.user_id == user.id)))
    solved = [a for a in aggregates.values() if a.solved]
    to_import = [a for a in solved if problem_ids[a.external_id] not in existing_solved]
    skipped = len(solved) - len(to_import)

    if to_import:
        to_import.sort(key=lambda a: (a.first_ok_at or now, a.external_id))
        for batch in _chunks(
            [
                {
                    "user_id": user.id,
                    "problem_id": problem_ids[a.external_id],
                    "solved_at": a.first_ok_at,
                    "source": SolveSource.codeforces,
                }
                for a in to_import
            ]
        ):
            db.execute(pg_insert(Solve).values(list(batch)).on_conflict_do_nothing())
        _create_cards(db, user, to_import, problem_ids, now)

    db.commit()
    return ImportResult(
        imported=len(to_import), skipped=skipped, attempts_recorded=attempts_recorded
    )


def _ensure_problems(db: Session, aggregates: dict[str, ProblemAggregate]) -> dict[str, int]:
    """Create missing problems (+ their tags) in bulk; existing problems are left untouched."""
    external_ids = list(aggregates)
    existing = {
        ext: pid
        for ext, pid in db.execute(
            select(Problem.external_id, Problem.id).where(
                Problem.platform == Platform.codeforces, Problem.external_id.in_(external_ids)
            )
        )
    }
    missing = [aggregates[e] for e in external_ids if e not in existing]
    if missing:
        new_ids: dict[str, int] = {}
        for batch in _chunks(missing):
            rows = db.execute(
                pg_insert(Problem)
                .values(
                    [
                        {
                            "platform": Platform.codeforces,
                            "external_id": a.external_id,
                            "title": a.title[:500],
                            "url": a.url,
                            "rating": a.rating,
                        }
                        for a in batch
                    ]
                )
                .on_conflict_do_nothing(index_elements=["platform", "external_id"])
                .returning(Problem.external_id, Problem.id)
            )
            new_ids.update({ext: pid for ext, pid in rows})
        # rows lost to a concurrent insert were not returned: look them up
        lost = [a.external_id for a in missing if a.external_id not in new_ids]
        if lost:
            for ext, pid in db.execute(
                select(Problem.external_id, Problem.id).where(
                    Problem.platform == Platform.codeforces, Problem.external_id.in_(lost)
                )
            ):
                existing[ext] = pid
        existing.update(new_ids)
        _attach_tags(db, [a for a in missing if a.external_id in new_ids], new_ids)
    return existing


def _attach_tags(db: Session, new_problems: list[ProblemAggregate], ids: dict[str, int]) -> None:
    names = sorted({t for a in new_problems for t in a.tags})
    if not names:
        return
    db.execute(pg_insert(Tag).values([{"name": n} for n in names]).on_conflict_do_nothing())
    tag_ids = {
        name: tid for name, tid in db.execute(select(Tag.name, Tag.id).where(Tag.name.in_(names)))
    }
    links = [
        {"problem_id": ids[a.external_id], "tag_id": tag_ids[t]}
        for a in new_problems
        for t in a.tags
    ]
    for batch in _chunks(links):
        db.execute(pg_insert(problem_tags).values(list(batch)).on_conflict_do_nothing())


def _upsert_attempts(
    db: Session, user: User, aggregates: dict[str, ProblemAggregate], ids: dict[str, int]
) -> int:
    """Insert/update attempt stats; returns how many rows were new or changed."""
    current = {
        row.problem_id: (row.tries, row.solved, row.first_attempt_at)
        for row in db.scalars(select(AttemptStat).where(AttemptStat.user_id == user.id))
    }
    rows = []
    for agg in aggregates.values():
        assert agg.first_attempt_at is not None
        value = (agg.tries, agg.solved, agg.first_attempt_at)
        if current.get(ids[agg.external_id]) != value:
            rows.append(
                {
                    "user_id": user.id,
                    "problem_id": ids[agg.external_id],
                    "tries": agg.tries,
                    "solved": agg.solved,
                    "first_attempt_at": agg.first_attempt_at,
                }
            )
    for batch in _chunks(rows):
        stmt = pg_insert(AttemptStat).values(list(batch))
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=["user_id", "problem_id"],
                set_={
                    "tries": stmt.excluded.tries,
                    "solved": stmt.excluded.solved,
                    "first_attempt_at": stmt.excluded.first_attempt_at,
                },
            )
        )
    return len(rows)


def _create_cards(
    db: Session,
    user: User,
    imported: list[ProblemAggregate],
    ids: dict[str, int],
    now: datetime,
) -> None:
    zone = ZoneInfo(user.timezone)
    today = now.astimezone(zone).date()
    have_card = set(db.scalars(select(ReviewCard.problem_id).where(ReviewCard.user_id == user.id)))
    todo = [a for a in imported if ids[a.external_id] not in have_card]
    if not todo:
        return
    occupied: dict[date, int] = defaultdict(int)
    for due, count in db.execute(
        select(ReviewCard.due_date, func.count())
        .where(
            ReviewCard.user_id == user.id,
            ReviewCard.repetitions == 0,
            ReviewCard.due_date >= today,
        )
        .group_by(ReviewCard.due_date)
    ):
        occupied[due] = count
    earliest = []
    for agg in todo:
        assert agg.first_ok_at is not None  # only solved problems are imported
        earliest.append(first_review_date(agg.first_ok_at.astimezone(zone).date(), today))
    due_dates = assign_due_dates(earliest, occupied)
    cards = [
        {
            "user_id": user.id,
            "problem_id": ids[a.external_id],
            "ease": 2.5,
            "interval_days": 0,
            "repetitions": 0,
            "lapses": 0,
            "due_date": due,
        }
        for a, due in zip(todo, due_dates, strict=True)
    ]
    for batch in _chunks(cards):
        db.execute(pg_insert(ReviewCard).values(list(batch)).on_conflict_do_nothing())
