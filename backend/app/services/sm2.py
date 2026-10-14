"""SM-2 spaced-repetition scheduler (pure functions, no database)."""

import math
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Protocol

MIN_EASE = 1.3
INITIAL_EASE = 2.5
PASS_THRESHOLD = 3

# UI buttons -> SM-2 quality grades
BUTTON_QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}


@dataclass(frozen=True)
class CardState:
    ease: float
    interval_days: int
    repetitions: int
    lapses: int
    due_date: date


def new_card(due_date: date) -> CardState:
    return CardState(ease=INITIAL_EASE, interval_days=0, repetitions=0, lapses=0, due_date=due_date)


class Scheduler(Protocol):
    """Interface so the algorithm can be swapped (e.g. for FSRS) without touching callers."""

    def schedule(self, card: CardState, quality: int, today: date) -> CardState: ...


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


class SM2Scheduler:
    def schedule(self, card: CardState, quality: int, today: date) -> CardState:
        if not 0 <= quality <= 5:
            raise ValueError("quality must be in 0..5")

        if quality < PASS_THRESHOLD:
            return replace(
                card,
                repetitions=0,
                interval_days=1,
                lapses=card.lapses + 1,
                due_date=today + timedelta(days=1),
            )

        if card.repetitions == 0:
            interval = 1
        elif card.repetitions == 1:
            interval = 6
        else:
            # computed with the ease *before* this answer is applied
            interval = max(1, _round_half_up(card.interval_days * card.ease))

        miss = 5 - quality
        ease = max(MIN_EASE, card.ease + 0.1 - miss * (0.08 + miss * 0.02))
        return replace(
            card,
            ease=ease,
            interval_days=interval,
            repetitions=card.repetitions + 1,
            due_date=today + timedelta(days=interval),
        )


_default_scheduler: Scheduler = SM2Scheduler()


def schedule(card: CardState, quality: int, today: date) -> CardState:
    return _default_scheduler.schedule(card, quality, today)


def preview_intervals(card: CardState, today: date) -> dict[str, int]:
    """Days until the next review for each UI button, shown on the buttons."""
    return {
        name: schedule(card, quality, today).interval_days
        for name, quality in BUTTON_QUALITY.items()
    }
