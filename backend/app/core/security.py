"""Password hashing and JWT handling.

Uses the `bcrypt` library directly instead of `passlib`.  Passlib (1.7.4) is
unmaintained and breaks on bcrypt >= 4.1 because it tries to inspect
`bcrypt.__about__.__version__`, which modern bcrypt releases no longer
provide.  Going direct also removes a dependency layer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from .config import get_settings

settings = get_settings()

# bcrypt silently truncates input > 72 bytes (pre-5.0) or raises (5.0+).  We
# match the old behaviour by hard-capping the byte length ourselves so the
# same password always produces a stable hash.
_BCRYPT_MAX_BYTES = 72


def _to_bytes(password: str) -> bytes:
    b = password.encode("utf-8")
    return b[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Return a bcrypt hash string for the given password."""
    hashed = bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time compare against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed / legacy hash — treat as a failed login rather than 500.
        return False


def create_access_token(
    subject: str,
    extra: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra:
        to_encode.update(extra)
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
