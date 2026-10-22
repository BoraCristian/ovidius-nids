"""Login / me / change-password endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, Token, UserOut
from app.api.deps import get_current_user

log = logging.getLogger("nids.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)) -> Token:
    """
    Verify credentials and mint a JWT.

    Wrapped in a broad try/except so a transient startup glitch (e.g. the
    database session firing before `init_db` finished on a very cold boot)
    surfaces as a clean 503 the frontend can retry, instead of an opaque 500.
    """
    settings = get_settings()
    try:
        res = await db.execute(select(User).where(User.username == form.username))
        user = res.scalar_one_or_none()
    except Exception as exc:
        log.exception("Login DB lookup failed (likely a startup race)")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Backend is still warming up. Please try again in a moment.",
        ) from exc

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    token = create_access_token(subject=user.username, extra={"role": user.role})
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Let a signed-in user rotate their own password."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect.")
    if len(payload.new_password) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be at least 4 characters.")
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
