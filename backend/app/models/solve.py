from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import SolveSource
from app.models.problem import Problem


class Solve(Base):
    __tablename__ = "solves"
    __table_args__ = (
        UniqueConstraint("user_id", "problem_id"),
        Index("ix_solves_user_id_solved_at", "user_id", "solved_at"),
        CheckConstraint("char_length(notes) <= 2000", name="notes_len"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    solved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[SolveSource] = mapped_column(Enum(SolveSource, name="solve_source"))
    time_spent_min: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)

    problem: Mapped[Problem] = relationship(lazy="joined")


class AttemptStat(Base):
    __tablename__ = "attempt_stats"
    __table_args__ = (UniqueConstraint("user_id", "problem_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    tries: Mapped[int]
    solved: Mapped[bool] = mapped_column(Boolean)
    first_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
