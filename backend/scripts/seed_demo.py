"""Create the demo account with a SYNTHETIC six-month history.

Usage (from `backend/`):  uv run python -m scripts.seed_demo

Everything created here is invented: problem names, ratings, dates and review answers are
generated from a fixed random seed. Running it again resets the demo user's data.
Login: demo@example.com / demo12345
"""

import random
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.models import Platform, ReviewCard, ReviewLog, Solve, SolveSource, User
from app.security import hash_password
from app.services import sm2
from app.services.solves import create_solve, get_or_create_problem, local_date, user_zone

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo12345"
HISTORY_DAYS = 183
OVERDUE_CARDS = 6
SKIP_PROBABILITY = 0.015

TOPICS = {
    "dp": ["Knapsack variation", "Longest path in a grid", "Coin change twist", "Stairs counting"],
    "greedy": ["Meeting rooms", "Fuel stops", "Sort by deadline", "Minimal swaps"],
    "graphs": ["Shortest route", "Connected islands", "Cycle detection", "Bridge hunting"],
    "math": ["Divisor games", "Modular puzzle", "Prime sieve task", "Digit sums"],
    "strings": ["Palindrome pairs", "Prefix function drill", "Anagram groups", "Longest border"],
    "binary search": ["Minimal capacity", "Search on answer", "Kth smallest"],
    "data structures": ["Range sum queries", "Monotonic stack", "Union-find tasks"],
    "implementation": ["Simulation of a queue", "Matrix rotation", "Calendar maths"],
    "trees": ["LCA queries", "Subtree sizes", "Tree diameter"],
}
# How strong the demo user is in each topic (higher = better review answers).
STRENGTH = {
    "dp": 0.25,
    "greedy": 0.7,
    "graphs": 0.4,
    "math": 0.75,
    "strings": 0.5,
    "binary search": 0.8,
    "data structures": 0.6,
    "implementation": 0.9,
    "trees": 0.35,
}
PLATFORMS = [Platform.codeforces, Platform.leetcode, Platform.yandex, Platform.other]


def _reset_user(db: Session) -> User:
    db.execute(delete(User).where(User.email == DEMO_EMAIL))  # cascades to all user data
    user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), cf_handle=None)
    db.add(user)
    db.flush()
    return user


def seed(db: Session, now: datetime | None = None, seed_value: int = 42) -> User:
    rng = random.Random(seed_value)
    now = now or datetime.now(UTC)
    user = _reset_user(db)
    zone = user_zone(user)
    today = local_date(now, zone)

    # Weekly intensity varies a lot: quiet weeks, bursts and a recent streak.
    weeks = HISTORY_DAYS // 7 + 1
    intensity = [rng.choice([0.0, 0.15, 0.35, 0.5, 0.7, 0.9]) for _ in range(weeks)]
    problems_created = 0
    for offset in range(HISTORY_DAYS, -1, -1):
        day = today - timedelta(days=offset)
        weekly = intensity[offset // 7]
        recent_streak = offset <= 4
        if not recent_streak and rng.random() > weekly:
            continue
        for _ in range(1 if recent_streak else rng.choice([1, 1, 1, 2, 3, 5])):
            topic = rng.choices(list(TOPICS), weights=[1 + 2 * (1 - STRENGTH[t]) for t in TOPICS])[
                0
            ]
            tags = [topic] + rng.sample([t for t in TOPICS if t != topic], rng.choice([0, 0, 1]))
            problems_created += 1
            platform = rng.choice(PLATFORMS)
            moment = datetime(
                day.year, day.month, day.day, rng.randint(8, 22), rng.randint(0, 59), tzinfo=zone
            )
            moment = min(moment, now - timedelta(minutes=1))  # never in the future
            problem = get_or_create_problem(
                db,
                platform=platform,
                external_id=f"demo-{problems_created:04d}",
                title=f"[demo] {rng.choice(TOPICS[topic])} #{problems_created}",
                url=None,
                rating=rng.choice(range(800, 2000, 100)),
                tags=tags,
            )
            create_solve(
                db,
                user,
                problem=problem,
                solved_at=moment.astimezone(UTC),
                source=SolveSource.manual,
                time_spent_min=rng.choice([10, 20, 35, 50, 90]),
                notes=rng.choice([None, None, "Synthetic demo note: key idea goes here."]),
                today=today,
                now=now,
            )
    db.flush()
    _simulate_reviews(db, user, rng, now, today)
    db.commit()
    return user


def _simulate_reviews(
    db: Session, user: User, rng: random.Random, now: datetime, today: date
) -> None:
    """Replay a plausible review history for every card, then leave a few cards overdue.

    Each card follows the SM-2 chain from the day after it was solved up to today. The simulated
    user occasionally skips a review (the card then stays overdue); answer quality depends on how
    strong the user is in the problem's topics.
    """
    zone = user_zone(user)
    solved_on = {
        problem_id: local_date(moment, zone)
        for problem_id, moment in db.execute(
            select(Solve.problem_id, Solve.solved_at).where(Solve.user_id == user.id)
        )
    }
    cards = list(db.scalars(select(ReviewCard).where(ReviewCard.user_id == user.id)).unique())
    for card in cards:
        strength = (
            max(STRENGTH.get(t.name, 0.5) for t in card.problem.tags) if card.problem.tags else 0.5
        )
        state = sm2.new_card(card.due_date)
        review_day = solved_on[card.problem_id] + timedelta(days=1)
        while review_day <= today and rng.random() > SKIP_PROBABILITY:
            quality = rng.choices([1, 3, 4, 5], weights=[1 - strength, 1, 1 + strength, strength])[
                0
            ]
            state = sm2.schedule(state, quality, review_day)
            db.add(
                ReviewLog(
                    card_id=card.id,
                    reviewed_at=datetime.combine(review_day, time(18, 0), tzinfo=zone).astimezone(
                        UTC
                    ),
                    quality=quality,
                    interval_after=state.interval_days,
                    ease_after=state.ease,
                )
            )
            card.last_reviewed_at = datetime.combine(review_day, time(18, 0), tzinfo=zone)
            review_day = state.due_date
        if state.repetitions or state.lapses:
            card.ease, card.interval_days = state.ease, state.interval_days
            card.repetitions, card.lapses, card.due_date = (
                state.repetitions,
                state.lapses,
                state.due_date,
            )
        else:  # never reviewed: first review is due the day after solving (or today)
            card.due_date = max(solved_on[card.problem_id] + timedelta(days=1), today)

    # Guarantee a handful of clearly overdue cards for the demo.
    upcoming = [c for c in cards if c.due_date >= today]
    for k, card in enumerate(rng.sample(upcoming, min(OVERDUE_CARDS, len(upcoming))), start=1):
        card.due_date = today - timedelta(days=k)


def main() -> None:
    with get_sessionmaker()() as db:
        user = seed(db)
        solves = len(list(db.scalars(select(Solve).where(Solve.user_id == user.id))))
        print(
            f"Seeded SYNTHETIC demo data: {solves} solves "
            f"(login {DEMO_EMAIL} / password {DEMO_PASSWORD})"
        )


if __name__ == "__main__":
    main()
