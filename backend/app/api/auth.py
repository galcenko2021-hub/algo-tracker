from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession
from app.config import get_settings
from app.models import User
from app.ratelimit import AUTH_LIMIT, limiter
from app.schemas.auth import Credentials, TokenOut, UserOut
from app.security import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, user_id: int) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        create_token(user_id, "refresh"),
        max_age=settings.refresh_token_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path=_COOKIE_PATH,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_LIMIT)
def register(request: Request, body: Credentials, db: DbSession) -> User:
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь с таким email уже существует")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Пользователь с таким email уже существует"
        ) from None
    return user


@router.post("/login", response_model=TokenOut)
@limiter.limit(AUTH_LIMIT)
def login(request: Request, body: Credentials, response: Response, db: DbSession) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email))
    # Same message and same work for "no such e-mail" and "wrong password".
    ok = verify_password(body.password, user.password_hash if user else None)
    if user is None or not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    _set_refresh_cookie(response, user.id)
    return TokenOut(access_token=create_token(user.id, "access"))


@router.post("/refresh", response_model=TokenOut)
@limiter.limit(AUTH_LIMIT)
def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    refresh_token: str | None = Cookie(default=None),
) -> TokenOut:
    user_id = decode_token(refresh_token, "refresh") if refresh_token else None
    if user_id is None or db.get(User, user_id) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия истекла, войдите заново")
    return TokenOut(access_token=create_token(user_id, "access"))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(AUTH_LIMIT)
def logout(request: Request, response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)
