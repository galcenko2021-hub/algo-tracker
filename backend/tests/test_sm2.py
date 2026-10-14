from datetime import date, timedelta

import pytest

from app.services.sm2 import (
    BUTTON_QUALITY,
    MIN_EASE,
    CardState,
    SM2Scheduler,
    new_card,
    preview_intervals,
    schedule,
)

TODAY = date(2026, 10, 14)


def run(qualities: list[int]) -> list[CardState]:
    """Apply answers one per day-of-due; returns the state after every answer."""
    card = new_card(TODAY)
    states = []
    today = TODAY
    for q in qualities:
        card = schedule(card, q, today)
        states.append(card)
        today = card.due_date
    return states


@pytest.mark.parametrize(
    ("qualities", "intervals", "eases"),
    [
        ([4, 4, 4, 4, 4], [1, 6, 15, 38, 95], [2.5, 2.5, 2.5, 2.5, 2.5]),
        ([5, 5, 5, 5], [1, 6, 16, 45], [2.6, 2.7, 2.8, 2.9]),
        ([3, 3, 3], [1, 6, 13], [2.36, 2.22, 2.08]),
        # failure resets the sequence but keeps ease
        ([4, 4, 4, 1, 4, 4], [1, 6, 15, 1, 1, 6], [2.5, 2.5, 2.5, 2.5, 2.5, 2.5]),
    ],
)
def test_expected_sequences(qualities: list[int], intervals: list[int], eases: list[float]) -> None:
    states = run(qualities)
    assert [s.interval_days for s in states] == intervals
    assert [s.ease for s in states] == pytest.approx(eases)


def test_due_date_is_today_plus_interval() -> None:
    card = schedule(new_card(TODAY), 4, TODAY)
    assert card.due_date == TODAY + timedelta(days=1)
    card = schedule(card, 4, TODAY + timedelta(days=1))
    assert card.due_date == TODAY + timedelta(days=7)


@pytest.mark.parametrize("quality", [0, 1, 2])
def test_failing_grades_reset_and_count_lapse(quality: int) -> None:
    card = CardState(ease=2.1, interval_days=40, repetitions=5, lapses=1, due_date=TODAY)
    result = schedule(card, quality, TODAY)
    assert result.repetitions == 0
    assert result.interval_days == 1
    assert result.lapses == 2
    assert result.ease == 2.1  # unchanged on failure
    assert result.due_date == TODAY + timedelta(days=1)


def test_ease_never_drops_below_floor() -> None:
    card = CardState(ease=1.35, interval_days=10, repetitions=4, lapses=0, due_date=TODAY)
    for _ in range(5):
        card = schedule(card, 3, TODAY)
    assert card.ease == MIN_EASE


def test_ease_floor_boundary_exact() -> None:
    card = CardState(ease=1.44, interval_days=10, repetitions=4, lapses=0, due_date=TODAY)
    assert schedule(card, 3, TODAY).ease == pytest.approx(1.3)  # 1.44 - 0.14
    card = CardState(ease=1.43, interval_days=10, repetitions=4, lapses=0, due_date=TODAY)
    assert schedule(card, 3, TODAY).ease == MIN_EASE  # would be 1.29


def test_ease_unchanged_by_failure_even_at_floor() -> None:
    card = CardState(ease=MIN_EASE, interval_days=3, repetitions=2, lapses=0, due_date=TODAY)
    assert schedule(card, 0, TODAY).ease == MIN_EASE


def test_interval_uses_previous_ease_and_rounds_half_up() -> None:
    card = CardState(ease=2.5, interval_days=3, repetitions=2, lapses=0, due_date=TODAY)
    assert schedule(card, 4, TODAY).interval_days == 8  # 7.5 -> 8
    card = CardState(ease=2.5, interval_days=5, repetitions=2, lapses=0, due_date=TODAY)
    assert schedule(card, 4, TODAY).interval_days == 13  # 12.5 -> 13 (not banker's 12)


def test_invalid_quality_rejected() -> None:
    for bad in (-1, 6):
        with pytest.raises(ValueError):
            schedule(new_card(TODAY), bad, TODAY)


def test_schedule_does_not_mutate_input() -> None:
    card = new_card(TODAY)
    schedule(card, 5, TODAY)
    assert card == new_card(TODAY)


def test_preview_intervals_match_buttons() -> None:
    assert BUTTON_QUALITY == {"again": 1, "hard": 3, "good": 4, "easy": 5}
    card = CardState(ease=2.5, interval_days=6, repetitions=2, lapses=0, due_date=TODAY)
    preview = preview_intervals(card, TODAY)
    # the interval is computed with the old ease, so passing grades only differ via later ease
    assert preview == {"again": 1, "hard": 15, "good": 15, "easy": 15}
    first = preview_intervals(new_card(TODAY), TODAY)
    assert first == {"again": 1, "hard": 1, "good": 1, "easy": 1}


def test_scheduler_is_swappable() -> None:
    class FixedScheduler:
        def schedule(self, card: CardState, quality: int, today: date) -> CardState:
            return CardState(2.5, 99, card.repetitions + 1, card.lapses, today)

    scheduler = FixedScheduler()
    assert scheduler.schedule(new_card(TODAY), 4, TODAY).interval_days == 99
    assert isinstance(SM2Scheduler().schedule(new_card(TODAY), 4, TODAY), CardState)
