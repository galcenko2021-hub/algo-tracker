from datetime import date

from pydantic import BaseModel, Field

from app.schemas.solves import ProblemOut


class NextIntervals(BaseModel):
    again: int
    hard: int
    good: int
    easy: int


class DueCard(BaseModel):
    card_id: int
    problem: ProblemOut
    notes: str | None
    due_date: date
    interval_days: int
    repetitions: int
    lapses: int
    ease: float
    next_intervals: NextIntervals


class DueResponse(BaseModel):
    count: int
    cards: list[DueCard]


class AnswerIn(BaseModel):
    quality: int = Field(ge=0, le=5)


class AnswerOut(BaseModel):
    card_id: int
    interval_days: int
    due_date: date
    ease: float
    repetitions: int
    lapses: int


class UpcomingDay(BaseModel):
    date: date
    count: int
