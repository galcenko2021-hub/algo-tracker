from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession, Now
from app.services.catalog import ensure_catalog
from app.services.codeforces import CodeforcesClient, CodeforcesError, get_codeforces_client
from app.services.recommender import data
from app.services.recommender.base import Recommendation, Recommender
from app.services.recommender.heuristic import HeuristicRecommender
from app.services.recommender.ml import MLRecommender, insufficient_data_reason, train_model

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendedProblem(BaseModel):
    external_id: str
    title: str
    url: str
    rating: int | None
    tags: list[str]
    solved_count: int


class RecommendationItem(BaseModel):
    problem: RecommendedProblem
    score: float
    reason: str
    predicted_solve_prob: float | None


class RecommendationsOut(BaseModel):
    method: Literal["ml", "heuristic"]
    fallback_reason: str | None
    level: int
    items: list[RecommendationItem]


def _item(rec: Recommendation) -> RecommendationItem:
    c = rec.candidate
    return RecommendationItem(
        problem=RecommendedProblem(
            external_id=c.external_id,
            title=c.title,
            url=c.url,
            rating=c.rating,
            tags=list(c.tags),
            solved_count=c.solved_count,
        ),
        score=round(rec.score, 4),
        reason=rec.reason,
        predicted_solve_prob=(
            None if rec.predicted_solve_prob is None else round(rec.predicted_solve_prob, 4)
        ),
    )


@router.get("", response_model=RecommendationsOut)
def get_recommendations(
    user: CurrentUser,
    db: DbSession,
    now: Now,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    client: CodeforcesClient = Depends(get_codeforces_client),
) -> RecommendationsOut:
    try:
        ensure_catalog(db, client, now)
    except CodeforcesError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Не удалось загрузить каталог задач Codeforces, попробуйте позже",
        ) from None

    candidates = data.load_candidates(db)
    ctx = data.load_context(db, user)
    samples = data.load_attempt_samples(db, user, candidates)

    fallback_reason = insufficient_data_reason(samples)
    recommender: Recommender
    method: Literal["ml", "heuristic"] = "heuristic"
    recs: list[Recommendation] = []
    if fallback_reason is None:
        trained = train_model(samples, ctx.level, data.tag_vocabulary(candidates))
        recs = MLRecommender(trained).recommend(ctx, candidates, limit)
        method = "ml"
        if not recs:
            fallback_reason = "ML не нашёл подходящих задач в каталоге, использована эвристика"
    if method == "heuristic" or not recs:
        recommender = HeuristicRecommender()
        recs = recommender.recommend(ctx, candidates, limit)
        method = "heuristic"
    return RecommendationsOut(
        method=method,
        fallback_reason=fallback_reason if method == "heuristic" else None,
        level=ctx.level,
        items=[_item(r) for r in recs],
    )
