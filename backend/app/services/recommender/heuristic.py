"""Level 1 recommender: weak topics + difficulty close to the user's level."""

from collections.abc import Sequence

from app.services.recommender.base import Candidate, Recommendation, UserContext

LOWER_MARGIN = 100
UPPER_MARGIN = 200
CLOSENESS_WEIGHT = 0.2
CLOSENESS_SCALE = 300


def closeness(rating: int, level: int) -> float:
    return 1 - abs(rating - (level + 100)) / CLOSENESS_SCALE


def rating_phrase(rating: int, level: int) -> str:
    if abs(rating - level) <= 100:
        return f"Рейтинг {rating} близок к вашему уровню {level}"
    if rating > level:
        return f"Рейтинг {rating} немного выше вашего уровня {level}: задача на рост"
    return f"Рейтинг {rating} ниже вашего уровня {level}: хорошая разминка"


def explain(ctx: UserContext, candidate: Candidate, rating: int) -> str:
    weakest = ctx.weakest_tag(candidate.tags)
    level_part = rating_phrase(rating, ctx.level)
    if weakest is None:
        return f"{level_part}."
    return f"Слабая тема: {ctx.describe_tag(weakest)}. {level_part}."


class HeuristicRecommender:
    def recommend(
        self, ctx: UserContext, candidates: Sequence[Candidate], limit: int
    ) -> list[Recommendation]:
        low, high = ctx.level - LOWER_MARGIN, ctx.level + UPPER_MARGIN
        scored: list[Recommendation] = []
        for candidate in candidates:
            rating = candidate.rating
            if rating is None or candidate.external_id in ctx.solved_ids:
                continue
            if not low <= rating <= high:
                continue
            score = ctx.weakness_sum(candidate.tags) + CLOSENESS_WEIGHT * closeness(
                rating, ctx.level
            )
            scored.append(Recommendation(candidate, score, explain(ctx, candidate, rating)))
        # ties: more popular (more solved) first, then id, so output is deterministic
        scored.sort(key=lambda r: (-r.score, -r.candidate.solved_count, r.candidate.external_id))
        return scored[:limit]
