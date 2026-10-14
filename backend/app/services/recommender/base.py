"""Shared types of the recommenders and the user-level estimate."""

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.services import stats
from app.services.stats import TagAggregate

DEFAULT_LEVEL = 800
LEVEL_WINDOW = 20


@dataclass(frozen=True)
class Candidate:
    external_id: str
    title: str
    url: str
    rating: int | None
    tags: Sequence[str]
    solved_count: int


@dataclass(frozen=True)
class Recommendation:
    candidate: Candidate
    score: float
    reason: str
    predicted_solve_prob: float | None = None


@dataclass(frozen=True)
class UserContext:
    level: int
    total_solved: int
    tags: Mapping[str, TagAggregate]
    solved_ids: frozenset[str]

    def weakness(self, tag: str) -> float:
        agg = self.tags.get(tag)
        if agg is None:
            return stats.weakness(0, self.total_solved, 0.0, 0)
        return stats.weakness(agg.solved, self.total_solved, agg.quality_sum, agg.quality_count)

    def weakness_sum(self, tags: Sequence[str]) -> float:
        """Sum of topic weaknesses, normalised by sqrt(number of tags) so many tags don't win."""
        if not tags:
            return 0.0
        return float(sum(self.weakness(t) for t in tags) / math.sqrt(len(tags)))

    def weakest_tag(self, tags: Sequence[str]) -> str | None:
        return max(tags, key=lambda t: (self.weakness(t), t), default=None)

    def describe_tag(self, tag: str) -> str:
        agg = self.tags.get(tag)
        solved = agg.solved if agg else 0
        if agg and agg.quality_count:
            quality = f"средняя оценка повторений {agg.quality_sum / agg.quality_count:.1f}"
        else:
            quality = "повторений пока нет"
        return f"{tag} (решено {solved}, {quality})"


class Recommender(Protocol):
    def recommend(
        self, ctx: UserContext, candidates: Sequence[Candidate], limit: int
    ) -> list[Recommendation]: ...


def round_to_hundred(value: float) -> int:
    return int((value + 50) // 100 * 100)


def estimate_level(recent_ratings: Sequence[int]) -> int:
    """Median rating of the latest solved rated problems (newest first), rounded to 100."""
    window = list(recent_ratings)[:LEVEL_WINDOW]
    if not window:
        return DEFAULT_LEVEL
    return round_to_hundred(statistics.median(window))
