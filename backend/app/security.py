from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

TokenType = Literal["access", "refresh"]

_hasher = PasswordHasher()
# Verified against when the e-mail is unknown, so login timing does not reveal account existence.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id: int, token_type: TokenType, now: datetime | None = None) -> str:
    settings = get_settings()
    issued = now or datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": int(issued.timestamp()),
        "exp": int((issued + lifetime).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> int | None:
    """Return the user id for a valid token of the expected type, otherwise None."""
    try:
        payload = jwt.decode(
            token, get_settings().secret_key, algorithms=[_ALGORITHM], options={"require": ["exp"]}
        )
        if payload.get("type") != expected_type:
            return None
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
