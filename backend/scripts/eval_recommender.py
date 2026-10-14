"""Offline evaluation of the ML recommender on SYNTHETIC data.

Usage (from `backend/`):  uv run python -m scripts.eval_recommender [--seeds 20] [--n 400]

No real user data is involved. A simulated user has a hidden skill that grows over time, a hidden
affinity for each topic and a bias towards trying problems close to their level. Attempts are
split chronologically (first 80% train, last 20% test) and the per-user logistic regression is
compared with a baseline that only knows `rating - level`.

The numbers describe how well the pipeline recovers a *simulated* signal. They say nothing about
real users: see the limitations section of the README.
"""

import argparse
import math
import random
import statistics
from datetime import UTC, datetime, timedelta

from app.services.recommender.base import estimate_level
from app.services.recommender.ml import (
    AttemptSample,
    EvalMetrics,
    evaluate,
    insufficient_data_reason,
)

TAGS = [
    "dp",
    "greedy",
    "math",
    "graphs",
    "strings",
    "trees",
    "binary search",
    "data structures",
    "geometry",
    "number theory",
    "implementation",
    "constructive algorithms",
]
START = datetime(2025, 1, 1, tzinfo=UTC)


def make_synthetic_samples(n: int, seed: int) -> list[AttemptSample]:
    """Simulate `n` attempts of one user. Deterministic for a given seed."""
    rng = random.Random(seed)
    affinity = {tag: rng.gauss(0, 150) for tag in TAGS}  # rating points of tag-specific skill
    skill_start, skill_gain = rng.uniform(1000, 1500), rng.uniform(100, 400)
    samples = []
    for i in range(n):
        progress = i / max(1, n - 1)
        skill = skill_start + skill_gain * progress
        # selection bias: the user mostly picks problems around their current level
        rating = int(round(rng.gauss(skill + 50, 250) / 100) * 100)
        rating = min(3000, max(800, rating))
        tags = rng.sample(TAGS, rng.randint(1, 3))
        solved_count = int(math.exp(rng.gauss(9.5 - (rating - 800) / 500, 0.8)))
        effective = skill + sum(affinity[t] for t in tags) / len(tags)
        p_solve = 1 / (1 + math.exp(-(effective - rating) / 150))
        samples.append(
            AttemptSample(
                rating=rating,
                tags=tags,
                solved_count=solved_count,
                solved=rng.random() < p_solve,
                first_attempt_at=START + timedelta(hours=7 * i),
            )
        )
    return samples


def level_of(samples: list[AttemptSample]) -> int:
    solved_newest_first = [
        s.rating
        for s in sorted(samples, key=lambda s: s.first_attempt_at, reverse=True)
        if s.solved
    ]
    return estimate_level(solved_newest_first)


def run(n: int, seeds: int) -> list[EvalMetrics]:
    results = []
    for seed in range(seeds):
        samples = make_synthetic_samples(n, seed)
        if insufficient_data_reason(samples) is not None:
            continue
        results.append(evaluate(samples, level_of(samples), TAGS))
    return results


def _fmt(values: list[float]) -> str:
    spread = statistics.pstdev(values) if len(values) > 1 else 0.0
    return f"{statistics.mean(values):.3f} ± {spread:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--seeds", type=int, default=20, help="number of simulated users")
    parser.add_argument("--n", type=int, default=400, help="attempts per simulated user")
    args = parser.parse_args()

    results = run(args.n, args.seeds)
    print("=== SYNTHETIC DATA: simulated users, not real people ===")
    print(f"simulated users: {len(results)}, attempts per user: {args.n}")
    if not results:
        print("not enough data to train the model")
        return
    print(f"split: chronological, train {results[0].n_train} / test {results[0].n_test}")
    rows = [
        ("ROC-AUC (higher is better)", "roc_auc", "baseline_roc_auc"),
        ("log-loss (lower is better)", "log_loss", "baseline_log_loss"),
    ]
    print(f"{'metric':32} {'model':>16} {'baseline (rating-level only)':>30}")
    for label, model_attr, base_attr in rows:
        model_vals = [v for r in results if (v := getattr(r, model_attr)) is not None]
        base_vals = [v for r in results if (v := getattr(r, base_attr)) is not None]
        print(f"{label:32} {_fmt(model_vals):>16} {_fmt(base_vals):>30}")
    print(f"selected C (median): {statistics.median(r.c for r in results)}")


if __name__ == "__main__":
    main()
