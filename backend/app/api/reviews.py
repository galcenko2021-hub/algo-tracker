from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, Now, local_today
from app.models import ReviewCard, ReviewLog, Solve
from app.schemas.reviews import (
    AnswerIn,
    AnswerOut,
    DueCard,
    DueResponse,
    NextIntervals,
    UpcomingDay,
)
from app.schemas.solves import ProblemOut
from app.services import sm2

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _state(card: ReviewCard) -> sm2.CardState:
    return sm2.CardState(
        ease=card.ease,
        interval_days=card.interval_days,
        repetitions=card.repetitions,
        lapses=card.lapses,
        due_date=card.due_date,
    )


@router.get("/due", response_model=DueResponse)
def due_cards(
    user: CurrentUser,
    db: DbSession,
    now: Now,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> DueResponse:
    today = local_today(now, user)
    due = ReviewCard.user_id == user.id, ReviewCard.due_date <= today
    count = db.scalar(select(func.count()).select_from(ReviewCard).where(*due)) or 0
    rows = db.execute(
        select(ReviewCard, Solve.notes)
        .join(
            Solve,
            (Solve.problem_id == ReviewCard.problem_id) & (Solve.user_id == ReviewCard.user_id),
        )
        .where(*due)
        .order_by(ReviewCard.due_date, ReviewCard.id)
        .limit(limit)
    ).unique()
    cards = [
        DueCard(
            card_id=card.id,
            problem=ProblemOut.model_validate(card.problem),
            notes=notes,
            due_date=card.due_date,
            interval_days=card.interval_days,
            repetitions=card.repetitions,
            lapses=card.lapses,
            ease=card.ease,
            next_intervals=NextIntervals(**sm2.preview_intervals(_state(card), today)),
        )
        for card, notes in rows
    ]
    return DueResponse(count=count, cards=cards)


@router.post("/{card_id}/answer", response_model=AnswerOut)
def answer(card_id: int, body: AnswerIn, user: CurrentUser, db: DbSession, now: Now) -> AnswerOut:
    card = db.scalar(
        select(ReviewCard).where(ReviewCard.id == card_id, ReviewCard.user_id == user.id)
    )
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Карточка не найдена")
    new = sm2.schedule(_state(card), body.quality, local_today(now, user))
    card.ease = new.ease
    card.interval_days = new.interval_days
    card.repetitions = new.repetitions
    card.lapses = new.lapses
    card.due_date = new.due_date
    card.last_reviewed_at = now
    db.add(
        ReviewLog(
            card_id=card.id,
            reviewed_at=now,
            quality=body.quality,
            interval_after=new.interval_days,
            ease_after=new.ease,
        )
    )
    db.commit()
    return AnswerOut(
        card_id=card.id,
        interval_days=new.interval_days,
        due_date=new.due_date,
        ease=new.ease,
        repetitions=new.repetitions,
        lapses=new.lapses,
    )


@router.get("/upcoming", response_model=list[UpcomingDay])
def upcoming(
    user: CurrentUser,
    db: DbSession,
    now: Now,
    days: Annotated[int, Query(ge=1, le=90)] = 14,
) -> list[UpcomingDay]:
    """Cards per day for `days` days starting today; overdue cards count towards today."""
    today = local_today(now, user)
    last = today + timedelta(days=days - 1)
    counts: dict[date, int] = {}
    for due_date, count in db.execute(
        select(ReviewCard.due_date, func.count())
        .where(ReviewCard.user_id == user.id, ReviewCard.due_date <= last)
        .group_by(ReviewCard.due_date)
    ):
        key = max(due_date, today)
        counts[key] = counts.get(key, 0) + count
    return [
        UpcomingDay(date=today + timedelta(days=i), count=counts.get(today + timedelta(days=i), 0))
        for i in range(days)
    ]
