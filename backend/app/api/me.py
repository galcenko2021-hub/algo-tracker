from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.auth import UserOut, UserPatch

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def get_me(user: CurrentUser) -> User:
    return user


@router.patch("", response_model=UserOut)
def patch_me(body: UserPatch, user: CurrentUser, db: DbSession) -> User:
    if "cf_handle" in body.model_fields_set:
        user.cf_handle = body.cf_handle
    if body.timezone is not None:
        user.timezone = body.timezone
    db.commit()
    return user
