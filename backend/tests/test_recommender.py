import math
import random
from datetime import UTC, datetime, timedelta

import pytest

from app.services.recommender.base import (
    Candidate,
    UserContext,
    estimate_level,
    round_to_hundred,
)
from app.services.recommender.heuristic import HeuristicRecommender, closeness
from app.services.recommender.ml import (
    MIN_PER_CLASS,
    MIN_SAMPLES,
    AttemptSample,
    MLRecommender,
    evaluate,
    featurize,
    insufficient_data_reason,
    train_model,
)
from app.services.stats import TagAggregate, weakness
from scripts.eval_recommender import TAGS, level_of, make_synthetic_samples


def cand(ext: str, rating: int | None, tags: list[str], solved_count: int = 1000) -> Candidate:
    return Candidate(ext, f"Problem {ext}", f"https://cf/{ext}", rating, tags, solved_count)


def agg(tag: str, solved: int, quality_sum: float = 0.0, quality_count: int = 0) -> TagAggregate:
    return TagAggregate(tag, solved, 0, 0, None, quality_sum, quality_count)


def ctx(level: int = 1100, total: int = 30, **tags: TagAggregate) -> UserContext:
    return UserContext(level=level, total_solved=total, tags=tags, solved_ids=frozenset({"1A"}))


# ---------- level estimate ----------


def test_estimate_level_defaults_and_rounding() -> None:
    assert estimate_level([]) == 800
    assert estimate_level([1000, 1200, 1400]) == 1200
    assert estimate_level([1100, 1200]) == 1200  # median 1150 -> up
    assert estimate_level([1000, 1099]) == 1000  # median 1049.5 -> down
    assert round_to_hundred(1150) == 1200 and round_to_hundred(1149) == 1100


def test_estimate_level_uses_only_last_twenty() -> None:
    newest_first = [1500] * 20 + [800] * 50
    assert estimate_level(newest_first) == 1500


# ---------- heuristic ----------


def test_closeness_peaks_at_level_plus_100() -> None:
    assert closeness(1200, 1100) == 1.0
    assert closeness(1000, 1100) == pytest.approx(1 - 200 / 300)


def test_heuristic_filters_candidates() -> None:
    candidates = [
        cand("1A", 1100, ["dp"]),  # already solved
        cand("2A", None, ["dp"]),  # no rating
        cand("3A", 900, ["dp"]),  # below level - 100
        cand("4A", 1400, ["dp"]),  # above level + 200
        cand("5A", 1000, ["dp"]),  # lower bound (inclusive)
        cand("6A", 1300, ["dp"]),  # upper bound (inclusive)
    ]
    recs = HeuristicRecommender().recommend(ctx(), candidates, limit=10)
    assert {r.candidate.external_id for r in recs} == {"5A", "6A"}


def test_heuristic_prefers_weak_topics_and_scores_by_formula() -> None:
    context = ctx(dp=agg("dp", 1, 2.0, 2), math=agg("math", 25, 4.5 * 10, 10))
    candidates = [cand("10A", 1200, ["math"]), cand("11A", 1200, ["dp"])]
    recs = HeuristicRecommender().recommend(context, candidates, limit=5)
    assert [r.candidate.external_id for r in recs] == ["11A", "10A"]
    expected = context.weakness("dp") + 0.2 * closeness(1200, 1100)
    assert recs[0].score == pytest.approx(expected)
    assert recs[0].predicted_solve_prob is None


def test_heuristic_normalises_by_sqrt_of_tag_count() -> None:
    context = ctx()
    w = context.weakness("x")  # same prior weakness for every unseen tag
    recs = HeuristicRecommender().recommend(
        context, [cand("20A", 1200, ["a", "b", "c", "d"])], limit=1
    )
    assert recs[0].score == pytest.approx(4 * w / 2 + 0.2)


def test_heuristic_untagged_candidate_scores_only_closeness() -> None:
    recs = HeuristicRecommender().recommend(ctx(), [cand("30A", 1200, [])], limit=1)
    assert recs[0].score == pytest.approx(0.2)
    assert "Слабая тема" not in recs[0].reason


def test_heuristic_reason_is_human_readable() -> None:
    context = ctx(dp=agg("dp", 3, 2.8 * 5, 5))
    rec = HeuristicRecommender().recommend(context, [cand("40A", 1200, ["dp"])], limit=1)[0]
    assert rec.reason == (
        "Слабая тема: dp (решено 3, средняя оценка повторений 2.8). "
        "Рейтинг 1200 близок к вашему уровню 1100."
    )
    no_reviews = ctx(dp=agg("dp", 3))
    rec = HeuristicRecommender().recommend(no_reviews, [cand("41A", 1300, ["dp"])], limit=1)[0]
    assert "повторений пока нет" in rec.reason
    assert "немного выше" in rec.reason


def test_heuristic_new_user_gets_results_and_limit_is_applied() -> None:
    empty = UserContext(level=800, total_solved=0, tags={}, solved_ids=frozenset())
    candidates = [cand(f"{i}A", 800 + 100 * (i % 3), ["dp"]) for i in range(10)]
    recs = HeuristicRecommender().recommend(empty, candidates, limit=3)
    assert len(recs) == 3
    assert HeuristicRecommender().recommend(empty, [], limit=3) == []


def test_heuristic_ties_are_deterministic() -> None:
    candidates = [
        cand("2B", 1200, ["dp"], 10),
        cand("1B", 1200, ["dp"], 10),
        cand("3B", 1200, ["dp"], 99),
    ]
    recs = HeuristicRecommender().recommend(ctx(), candidates, limit=3)
    assert [r.candidate.external_id for r in recs] == ["3B", "1B", "2B"]


# ---------- ML: data requirements ----------


def samples_with(n_pos: int, n_neg: int) -> list[AttemptSample]:
    base = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        AttemptSample(1200, ["dp"], 100, i < n_pos, base + timedelta(hours=i))
        for i in range(n_pos + n_neg)
    ]


def test_insufficient_data_reasons() -> None:
    assert insufficient_data_reason([]) is not None
    assert "100" in (insufficient_data_reason(samples_with(50, 49)) or "")
    too_few_pos = insufficient_data_reason(samples_with(MIN_PER_CLASS - 1, 100))
    assert too_few_pos is not None and "решённых 19" in too_few_pos
    too_few_neg = insufficient_data_reason(samples_with(100, MIN_PER_CLASS - 1))
    assert too_few_neg is not None and "нерешённых 19" in too_few_neg


def test_enough_data_boundary() -> None:
    assert insufficient_data_reason(samples_with(20, MIN_SAMPLES - 20)) is None
    assert insufficient_data_reason(samples_with(20, MIN_SAMPLES - 21)) is not None


# ---------- ML: features, evaluation, recommendation ----------


def test_featurize_layout() -> None:
    x = featurize([(1500, ["dp", "unknown"], 2718), (1100, [], 0)], 1100, ["dp", "math"])
    assert x.shape == (2, 4)
    assert x[0, 0] == pytest.approx(1.0)
    assert x[0, 1] == pytest.approx(math.log1p(2718) / 10)
    assert list(x[0, 2:]) == [1.0, 0.0]  # unknown tags are ignored
    assert x[1, 0] == 0.0 and x[1, 1] == 0.0 and not x[1, 2:].any()


def test_evaluate_uses_chronological_split_independent_of_input_order() -> None:
    samples = make_synthetic_samples(200, seed=3)
    level = level_of(samples)
    shuffled = samples[:]
    random.Random(0).shuffle(shuffled)
    a = evaluate(samples, level, TAGS)
    b = evaluate(shuffled, level, TAGS)
    assert (a.n_train, a.n_test) == (160, 40)
    assert a == b  # the order of input does not matter: split is by first_attempt_at


def test_split_never_leaks_future_into_training() -> None:
    # early attempts: always solved; late attempts: never solved. A model trained only on the
    # past cannot predict the future, which a shuffled split would hide.
    base = datetime(2025, 1, 1, tzinfo=UTC)
    samples = [
        AttemptSample(1200, ["dp"], 100, i < 100, base + timedelta(hours=i)) for i in range(200)
    ]
    metrics = evaluate(samples, 1200, ["dp"])
    assert metrics.n_train == 160
    assert metrics.log_loss > math.log(2)  # worse than a coin flip on the unseen future


def test_model_learns_signal_on_synthetic_user() -> None:
    samples = make_synthetic_samples(400, seed=1)
    assert insufficient_data_reason(samples) is None
    metrics = evaluate(samples, level_of(samples), TAGS)
    assert metrics.roc_auc is not None and metrics.roc_auc > 0.65
    assert metrics.log_loss < 0.68  # better than a coin flip (ln 2 ~ 0.693)


def test_synthetic_generator_is_deterministic() -> None:
    assert make_synthetic_samples(50, 7) == make_synthetic_samples(50, 7)
    assert make_synthetic_samples(50, 7) != make_synthetic_samples(50, 8)


def test_ml_recommender_targets_sixty_percent_and_weak_topics() -> None:
    samples = make_synthetic_samples(400, seed=1)
    level = level_of(samples)
    trained = train_model(samples, level, TAGS)
    context = UserContext(level=level, total_solved=40, tags={}, solved_ids=frozenset({"9Z"}))
    candidates = [
        cand(f"{i}X", level - 200 + 100 * (i % 6), [TAGS[i % len(TAGS)]]) for i in range(60)
    ]
    candidates.append(cand("9Z", level, ["dp"]))  # solved: must not be recommended
    candidates.append(cand("8Z", level + 1500, ["dp"]))  # out of range
    recs = MLRecommender(trained).recommend(context, candidates, limit=5)
    assert len(recs) == 5
    ids = {r.candidate.external_id for r in recs}
    assert "9Z" not in ids and "8Z" not in ids
    probabilities = [r.predicted_solve_prob for r in recs]
    assert all(p is not None and 0 <= p <= 1 for p in probabilities)
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)
    best = recs[0]
    expected = (
        context.weakness_sum(best.candidate.tags)
        + 1
        - abs((best.predicted_solve_prob or 0) - 0.6) / 0.6
    )
    assert best.score == pytest.approx(expected)
    assert "%" in best.reason

    # the pool is limited to unsolved problems around the level; empty pool -> no results
    assert MLRecommender(trained).recommend(context, [cand("1Q", None, ["dp"])], 5) == []


def test_weakness_prior_for_unseen_tag() -> None:
    assert ctx(total=0).weakness("anything") == pytest.approx(weakness(0, 0, 0, 0))
