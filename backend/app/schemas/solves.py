from datetime import UTC, datetime
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from app.models import Platform, SolveSource

_http_url = TypeAdapter(AnyHttpUrl)


def _check_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    # Only http(s) links are stored: the UI renders them as <a href>.
    _http_url.validate_python(value)
    return value


def _check_tags(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for raw in values:
        tag = " ".join(raw.strip().lower().split())
        if not tag:
            continue
        if len(tag) > 64:
            raise ValueError("Тег длиннее 64 символов")
        seen[tag] = None
    return list(seen)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SolveCreate(BaseModel):
    platform: Platform
    external_id: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=1000)
    rating: int | None = Field(default=None, ge=0, le=5000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    solved_at: datetime | None = None
    time_spent_min: int | None = Field(default=None, ge=0, le=100_000)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название не может быть пустым")
        return value

    @field_validator("external_id")
    @classmethod
    def strip_external_id(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value else None

    @field_validator("url")
    @classmethod
    def check_url(cls, value: str | None) -> str | None:
        return _check_url(value)

    @field_validator("tags")
    @classmethod
    def check_tags(cls, value: list[str]) -> list[str]:
        return _check_tags(value)

    @field_validator("solved_at")
    @classmethod
    def check_solved_at(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)


class SolvePatch(BaseModel):
    """Solve-level fields are always editable; problem-level ones only for private problems."""

    solved_at: datetime | None = None
    time_spent_min: int | None = Field(default=None, ge=0, le=100_000)
    notes: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=1000)
    rating: int | None = Field(default=None, ge=0, le=5000)
    tags: list[str] | None = Field(default=None, max_length=30)

    @field_validator("url")
    @classmethod
    def check_url(cls, value: str | None) -> str | None:
        return _check_url(value)

    @field_validator("tags")
    @classmethod
    def check_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _check_tags(value)

    @field_validator("solved_at")
    @classmethod
    def check_solved_at(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)


class ProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: Platform
    external_id: str
    title: str
    url: str | None
    rating: int | None
    tags: list[str]

    @field_validator("tags", mode="before")
    @classmethod
    def tag_names(cls, value: list[Any]) -> list[str]:
        return [t if isinstance(t, str) else str(t.name) for t in value]


class SolveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solved_at: datetime
    source: SolveSource
    time_spent_min: int | None
    notes: str | None
    problem: ProblemOut


class SolvePage(BaseModel):
    items: list[SolveOut]
    total: int
    page: int
    page_size: int
