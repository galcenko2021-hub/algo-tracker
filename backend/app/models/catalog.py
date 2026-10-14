from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CfCatalogEntry(Base):
    __tablename__ = "cf_catalog"

    external_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000))
    rating: Mapped[int | None]
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    solved_count: Mapped[int] = mapped_column(default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
