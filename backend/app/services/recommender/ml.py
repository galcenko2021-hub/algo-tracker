"""Level 2 recommender: a per-user logistic regression predicting "will the user solve it?".

The model is trained on the user's own `attempt_stats` (imported from Codeforces). It is a
heuristic aid, not a skill measurement: see the limitations section of the README.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

from app.services.recommender.base import Candidate, Recommendation, UserContext

MIN_SAMPLES = 100
MIN_PER_CLASS = 20
TRAIN_FRACTION = 0.8
C_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
CV_SPLITS = 4
TARGET_PROBABILITY = 0.6
LOWER_MARGIN = 200
UPPER_MARGIN = 300

Matrix = NDArray[np.float64]


@dataclass(frozen=True)
class AttemptSample:
    rating: int
    tags: Sequence[str]
    solved_count: int
    solved: bool
    first_attempt_at: datetime


@dataclass(frozen=True)
class EvalMetrics:
    n_train: int
    n_test: int
    c: float
    roc_auc: float | None
    log_loss: float
    baseline_roc_auc: float | None
    baseline_log_loss: float


def insufficient_data_reason(samples: Sequence[AttemptSample]) -> str | None:
    """None if the model may be trained, otherwise a human-readable reason (in Russian)."""
    positives = sum(1 for s in samples if s.solved)
    negatives = len(samples) - positives
    if len(samples) < MIN_SAMPLES:
        return (
            f"Мало данных для ML: {len(samples)} задач с попытками, нужно не меньше {MIN_SAMPLES}"
        )
    if positives < MIN_PER_CLASS or negatives < MIN_PER_CLASS:
        return (
            f"Мало данных для ML: решённых {positives}, нерешённых {negatives}, "
            f"нужно не меньше {MIN_PER_CLASS} каждого вида"
        )
    return None


def featurize(
    rows: Sequence[tuple[int, Sequence[str], int]], level: int, vocab: Sequence[str]
) -> Matrix:
    """Columns: (rating - level) / 400, log(1 + solved_count) / 10, multi-hot tags."""
    index = {tag: i + 2 for i, tag in enumerate(vocab)}
    matrix = np.zeros((len(rows), 2 + len(vocab)), dtype=np.float64)
    for r, (rating, tags, solved_count) in enumerate(rows):
        matrix[r, 0] = (rating - level) / 400
        matrix[r, 1] = math.log1p(max(solved_count, 0)) / 10
        for tag in tags:
            column = index.get(tag)
            if column is not None:
                matrix[r, column] = 1.0
    return matrix


def _fit(x: Matrix, y: NDArray[np.int_], c: float) -> LogisticRegression:
    model = LogisticRegression(C=c, max_iter=1000)  # L2 penalty is the default
    model.fit(x, y)
    return model


def _safe_auc(y_true: NDArray[np.int_], proba: NDArray[np.float64]) -> float | None:
    if len(set(y_true.tolist())) < 2:
        return None
    return float(roc_auc_score(y_true, proba))


def _loss(y_true: NDArray[np.int_], proba: NDArray[np.float64]) -> float:
    return float(log_loss(y_true, proba, labels=[0, 1]))


def select_c(x: Matrix, y: NDArray[np.int_]) -> float:
    """Pick C by expanding-window (time-ordered) cross-validation; rows must be time-sorted."""
    splitter = TimeSeriesSplit(n_splits=min(CV_SPLITS, max(2, len(y) // 20)))
    best_c, best_loss = 1.0, math.inf
    for c in C_GRID:
        losses = []
        for train_idx, val_idx in splitter.split(x):
            if len(set(y[train_idx].tolist())) < 2:
                continue
            model = _fit(x[train_idx], y[train_idx], c)
            losses.append(_loss(y[val_idx], model.predict_proba(x[val_idx])[:, 1]))
        if losses and (mean := sum(losses) / len(losses)) < best_loss:
            best_c, best_loss = c, mean
    return best_c


def _arrays(
    samples: Sequence[AttemptSample], level: int, vocab: Sequence[str]
) -> tuple[Matrix, NDArray[np.int_]]:
    ordered = sorted(samples, key=lambda s: s.first_attempt_at)
    x = featurize([(s.rating, s.tags, s.solved_count) for s in ordered], level, vocab)
    y = np.array([int(s.solved) for s in ordered], dtype=np.int_)
    return x, y


def evaluate(samples: Sequence[AttemptSample], level: int, vocab: Sequence[str]) -> EvalMetrics:
    """Chronological hold-out: first 80% (by first attempt) train, last 20% test."""
    x, y = _arrays(samples, level, vocab)
    split = int(len(y) * TRAIN_FRACTION)
    x_train, y_train, x_test, y_test = x[:split], y[:split], x[split:], y[split:]
    c = select_c(x_train, y_train)
    model = _fit(x_train, y_train, c)
    proba = model.predict_proba(x_test)[:, 1]
    baseline = _fit(x_train[:, :1], y_train, 1.0)
    base_proba = baseline.predict_proba(x_test[:, :1])[:, 1]
    return EvalMetrics(
        n_train=split,
        n_test=len(y) - split,
        c=c,
        roc_auc=_safe_auc(y_test, proba),
        log_loss=_loss(y_test, proba),
        baseline_roc_auc=_safe_auc(y_test, base_proba),
        baseline_log_loss=_loss(y_test, base_proba),
    )


@dataclass(frozen=True)
class TrainedModel:
    model: LogisticRegression
    vocab: Sequence[str]
    level: int
    c: float

    def predict(self, candidates: Sequence[Candidate]) -> NDArray[np.float64]:
        rows = [(c.rating or 0, c.tags, c.solved_count) for c in candidates]
        x = featurize(rows, self.level, self.vocab)
        return np.asarray(self.model.predict_proba(x)[:, 1], dtype=np.float64)


def train_model(samples: Sequence[AttemptSample], level: int, vocab: Sequence[str]) -> TrainedModel:
    """Fit on all available attempts (C chosen by time-ordered CV)."""
    x, y = _arrays(samples, level, vocab)
    c = select_c(x, y)
    return TrainedModel(model=_fit(x, y, c), vocab=list(vocab), level=level, c=c)


class MLRecommender:
    def __init__(self, trained: TrainedModel) -> None:
        self._trained = trained

    def recommend(
        self, ctx: UserContext, candidates: Sequence[Candidate], limit: int
    ) -> list[Recommendation]:
        low, high = ctx.level - LOWER_MARGIN, ctx.level + UPPER_MARGIN
        pool = [
            c
            for c in candidates
            if c.rating is not None
            and low <= c.rating <= high
            and c.external_id not in ctx.solved_ids
        ]
        if not pool:
            return []
        probabilities = self._trained.predict(pool)
        scored = []
        for candidate, p in zip(pool, probabilities, strict=True):
            probability = float(p)
            score = (
                ctx.weakness_sum(candidate.tags)
                + 1
                - abs(probability - TARGET_PROBABILITY) / TARGET_PROBABILITY
            )
            weakest = ctx.weakest_tag(candidate.tags)
            reason = (
                f"Модель оценивает шанс решить в {round(probability * 100)}% (цель — около 60%)."
            )
            if weakest is not None:
                reason += f" Слабая тема: {ctx.describe_tag(weakest)}."
            scored.append(Recommendation(candidate, score, reason, probability))
        scored.sort(key=lambda r: (-r.score, r.candidate.external_id))
        return scored[:limit]
