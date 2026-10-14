"""Pure statistics logic: streaks, heatmap, summary and topic weakness. No database access."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

PRIOR_QUALITY = 3.5
PRIOR_WEIGHT = 3
COVERAGE_TARGET = 0.15


def compute_streaks(days: Iterable[date], today: date) -> tuple[int, int]:
    """Return (current, longest) streak over local dates that have at least one solve.

    The current streak is not broken until the end of today: if nothing was solved today yet,
    counting starts from yesterday.
    """
    solved = set(days)
    if not solved:
        return 0, 0

    longest = run = 0
    previous: date | None = None
    for day in sorted(solved):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day

    cursor = today if today in solved else today - timedelta(days=1)
    current = 0
    while cursor in solved:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


@dataclass(frozen=True)
class Summary:
    total: int
    last_7_days: int
    last_30_days: int
    current_streak: int
    longest_streak: int


def summarize(counts: Mapping[date, int], today: date) -> Summary:
    """`counts` maps a local date to the number of solves on it."""
    window_7 = today - timedelta(days=6)
    window_30 = today - timedelta(days=29)
    current, longest = compute_streaks((d for d, c in counts.items() if c > 0), today)
    return Summary(
        total=sum(counts.values()),
        last_7_days=sum(c for d, c in counts.items() if window_7 <= d <= today),
        last_30_days=sum(c for d, c in counts.items() if window_30 <= d <= today),
        current_streak=current,
        longest_streak=longest,
    )


def build_heatmap(counts: Mapping[date, int], start: date, end: date) -> list[tuple[date, int]]:
    """Contiguous day-by-day series from `start` to `end` inclusive (zeros included)."""
    if end < start:
        return []
    return [
        (start + timedelta(days=offset), counts.get(start + timedelta(days=offset), 0))
        for offset in range((end - start).days + 1)
    ]


def smoothed_quality(quality_sum: float, quality_count: int) -> float:
    """Bayesian smoothing of the mean review quality towards the prior (3.5, weight 3)."""
    return (quality_sum + PRIOR_WEIGHT * PRIOR_QUALITY) / (quality_count + PRIOR_WEIGHT)


def weakness(
    solved_in_tag: int, total_solved: int, quality_sum: float, quality_count: int
) -> float:
    """Topic weakness in [0, 1]: rarely practised topics and poorly reviewed ones score higher."""
    coverage = solved_in_tag / total_solved if total_solved > 0 else 0.0
    quality = smoothed_quality(quality_sum, quality_count)
    value = 0.5 * (1 - min(1.0, coverage / COVERAGE_TARGET)) + 0.5 * (1 - quality / 5)
    return min(1.0, max(0.0, value))


@dataclass(frozen=True)
class TagAggregate:
    """Raw per-tag numbers loaded from the database for one user."""

    tag: str
    solved: int
    rating_sum: int
    rating_count: int
    last_solved_at: datetime | None
    quality_sum: float
    quality_count: int


@dataclass(frozen=True)
class TopicStat:
    tag: str
    solved: int
    share: float
    avg_rating: float | None
    last_solved_at: datetime | None
    avg_review_quality: float | None
    weakness: float


def topic_stats(aggregates: Iterable[TagAggregate], total_solved: int) -> list[TopicStat]:
    """Topic table, weakest first (ties: fewer solves first, then name)."""
    result = [
        TopicStat(
            tag=a.tag,
            solved=a.solved,
            share=a.solved / total_solved if total_solved > 0 else 0.0,
            avg_rating=a.rating_sum / a.rating_count if a.rating_count else None,
            last_solved_at=a.last_solved_at,
            avg_review_quality=a.quality_sum / a.quality_count if a.quality_count else None,
            weakness=weakness(a.solved, total_solved, a.quality_sum, a.quality_count),
        )
        for a in aggregates
    ]
    result.sort(key=lambda t: (-t.weakness, t.solved, t.tag))
    return result
