from datetime import UTC, date, datetime, timedelta

import pytest

from app.services.stats import (
    TagAggregate,
    build_heatmap,
    compute_streaks,
    smoothed_quality,
    summarize,
    topic_stats,
    weakness,
)

TODAY = date(2026, 10, 14)


def days(*offsets: int) -> list[date]:
    return [TODAY - timedelta(days=o) for o in offsets]


def test_streaks_empty() -> None:
    assert compute_streaks([], TODAY) == (0, 0)


def test_streak_including_today() -> None:
    assert compute_streaks(days(0, 1, 2), TODAY) == (3, 3)


def test_streak_not_broken_until_end_of_today() -> None:
    # nothing solved today yet: count from yesterday
    assert compute_streaks(days(1, 2, 3), TODAY) == (3, 3)


def test_streak_broken_after_missing_yesterday() -> None:
    assert compute_streaks(days(2, 3, 4), TODAY) == (0, 3)


def test_longest_streak_may_be_in_the_past() -> None:
    assert compute_streaks(days(0, 10, 11, 12, 13, 14), TODAY) == (1, 5)


def test_streak_across_month_and_year_boundary() -> None:
    today = date(2026, 1, 2)
    solved = [date(2025, 12, 30), date(2025, 12, 31), date(2026, 1, 1), date(2026, 1, 2)]
    assert compute_streaks(solved, today) == (4, 4)
    assert compute_streaks([date(2026, 2, 28), date(2026, 3, 1)], date(2026, 3, 1)) == (2, 2)


def test_streak_ignores_duplicates_and_future_days() -> None:
    assert compute_streaks([TODAY, TODAY, TODAY - timedelta(days=1)], TODAY) == (2, 2)
    assert compute_streaks([TODAY + timedelta(days=3)], TODAY) == (0, 1)


def test_summary_windows() -> None:
    counts = {
        TODAY: 2,
        TODAY - timedelta(days=6): 1,  # last day of the 7-day window
        TODAY - timedelta(days=7): 4,  # just outside
        TODAY - timedelta(days=29): 1,  # last day of the 30-day window
        TODAY - timedelta(days=30): 5,
    }
    s = summarize(counts, TODAY)
    assert (s.total, s.last_7_days, s.last_30_days) == (13, 3, 8)
    assert s.current_streak == 1


def test_summary_empty() -> None:
    s = summarize({}, TODAY)
    assert (s.total, s.last_7_days, s.last_30_days, s.current_streak, s.longest_streak) == (
        0,
        0,
        0,
        0,
        0,
    )


def test_heatmap_fills_zeros_and_is_inclusive() -> None:
    series = build_heatmap(
        {date(2026, 2, 28): 2, date(2026, 3, 1): 1}, date(2026, 2, 27), date(2026, 3, 2)
    )
    assert series == [
        (date(2026, 2, 27), 0),
        (date(2026, 2, 28), 2),
        (date(2026, 3, 1), 1),
        (date(2026, 3, 2), 0),
    ]
    assert build_heatmap({}, date(2026, 3, 2), date(2026, 3, 1)) == []
    assert len(build_heatmap({}, date(2025, 10, 15), TODAY)) == 365


def test_smoothed_quality_pulls_towards_prior() -> None:
    assert smoothed_quality(0, 0) == pytest.approx(3.5)
    assert smoothed_quality(5, 1) == pytest.approx((5 + 10.5) / 4)
    # many observations dominate the prior
    assert smoothed_quality(100 * 5, 100) == pytest.approx(510.5 / 103)


def test_weakness_formula() -> None:
    # no data: coverage 0 -> 0.5, quality prior 3.5 -> 0.5 * 0.3
    assert weakness(0, 0, 0, 0) == pytest.approx(0.5 + 0.15)
    # coverage at target (15%) and prior quality
    assert weakness(15, 100, 0, 0) == pytest.approx(0.15)
    # coverage above target is capped
    assert weakness(80, 100, 0, 0) == pytest.approx(0.15)
    # perfect reviews lower weakness, poor reviews raise it
    good = weakness(3, 100, 5 * 30, 30)
    bad = weakness(3, 100, 1 * 30, 30)
    assert good < weakness(3, 100, 0, 0) < bad
    assert 0 <= good <= bad <= 1


def test_topic_stats_sorted_by_weakness() -> None:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    aggs = [
        TagAggregate("dp", 3, 3600, 3, now, 3 * 2.0, 3),
        TagAggregate("math", 20, 0, 0, now, 0.0, 0),
        TagAggregate("graphs", 1, 1000, 1, None, 0.0, 0),
    ]
    topics = topic_stats(aggs, total_solved=24)
    assert [t.tag for t in topics] == ["graphs", "dp", "math"]
    dp = next(t for t in topics if t.tag == "dp")
    assert dp.avg_rating == pytest.approx(1200)
    assert dp.avg_review_quality == pytest.approx(2.0)
    assert dp.share == pytest.approx(3 / 24)
    math = next(t for t in topics if t.tag == "math")
    assert math.avg_rating is None and math.avg_review_quality is None
    assert topic_stats([], 0) == []
