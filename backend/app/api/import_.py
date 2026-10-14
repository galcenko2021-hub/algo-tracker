import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession, Now
from app.services.codeforces import (
    CodeforcesClient,
    CodeforcesNotFound,
    CodeforcesRateLimited,
    CodeforcesUnavailable,
    get_codeforces_client,
)
from app.services.importer import import_submissions

router = APIRouter(prefix="/import", tags=["import"])

_HANDLE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


class ImportIn(BaseModel):
    handle: str | None = None


class ImportOut(BaseModel):
    imported: int
    skipped: int
    attempts_recorded: int


@router.post("/codeforces", response_model=ImportOut)
def import_codeforces(
    user: CurrentUser,
    db: DbSession,
    now: Now,
    client: CodeforcesClient = Depends(get_codeforces_client),
    body: ImportIn | None = None,
) -> ImportOut:
    handle = ((body.handle if body else None) or user.cf_handle or "").strip()
    if not handle:
        raise HTTPException(422, "Укажите хэндл Codeforces в запросе или в настройках профиля")
    if not _HANDLE.match(handle):
        raise HTTPException(422, "Некорректный хэндл Codeforces")
    try:
        submissions = client.user_status(handle)
    except CodeforcesNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Пользователь Codeforces «{handle}» не найден"
        ) from None
    except CodeforcesRateLimited:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Codeforces ограничил число запросов, повторите через минуту",
        ) from None
    except CodeforcesUnavailable:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Codeforces сейчас недоступен, попробуйте позже"
        ) from None
    result = import_submissions(db, user, submissions, now)
    return ImportOut(
        imported=result.imported,
        skipped=result.skipped,
        attempts_recorded=result.attempts_recorded,
    )
