from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.problem import Problem


class ReviewCard(Base):
    __tablename__ = "review_cards"
    __table_args__ = (
        UniqueConstraint("user_id", "problem_id"),
        Index("ix_review_cards_user_id_due_date", "user_id", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(default=0)
    repetitions: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[date] = mapped_column(Date)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    problem: Mapped[Problem] = relationship(lazy="joined")


class ReviewLog(Base):
    __tablename__ = "review_log"
    __table_args__ = (CheckConstraint("quality between 0 and 5", name="quality_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("review_cards.id", ondelete="CASCADE"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quality: Mapped[int]
    interval_after: Mapped[int]
    ease_after: Mapped[float] = mapped_column(Float)
