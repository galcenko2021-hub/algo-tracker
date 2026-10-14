from datetime import date, datetime

from pydantic import BaseModel


class SummaryOut(BaseModel):
    total: int
    last_7_days: int
    last_30_days: int
    current_streak: int
    longest_streak: int


class HeatmapDay(BaseModel):
    date: date
    count: int


class TopicOut(BaseModel):
    tag: str
    solved: int
    share: float
    avg_rating: float | None
    last_solved_at: datetime | None
    avg_review_quality: float | None
    weakness: float
