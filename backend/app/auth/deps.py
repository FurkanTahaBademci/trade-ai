"""Kisisel uclar icin oturum dependency'si (`Authorization: Bearer <token>`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import resolve_session
from app.core.db import get_db
from app.models import AppUser, UserSession


@dataclass(frozen=True)
class AuthContext:
    user: AppUser
    session: UserSession


async def require_session(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    scheme, _, token = (authorization or "").partition(" ")
    resolved = (
        await resolve_session(db, token.strip()) if scheme.lower() == "bearer" and token else None
    )
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Oturum geçersiz ya da süresi dolmuş."},
        )
    return AuthContext(*resolved)


CurrentAuth = Annotated[AuthContext, Depends(require_session)]
