"""Yonetici: kullanici listesi, hesap durumu ve davet kodlari (/sistem ekrani)."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.schedules import require_admin_token
from app.auth.security import new_invite_code
from app.auth.service import registration_mode, revoke_sessions, utcnow
from app.core.db import get_db
from app.mail.sender import smtp_configured
from app.models import AppUser, InviteCode
from app.schemas.auth import AdminUserOut, AdminUsersOut, AdminUserUpdate, InviteCreate, InviteOut

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/users", response_model=AdminUsersOut)
async def list_users(db: DB, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> AdminUsersOut:
    since = utcnow() - timedelta(hours=24)
    total, verified, recent = (
        await db.execute(
            select(
                func.count(AppUser.id),
                func.count(AppUser.email_verified_at),
                func.count(AppUser.id).filter(AppUser.created_at >= since),
            )
        )
    ).one()
    users = await db.scalars(select(AppUser).order_by(AppUser.id.desc()).limit(limit))
    return AdminUsersOut(
        total=total,
        verified=verified,
        signups_24h=recent,
        smtp_configured=smtp_configured(),
        registration_mode=await registration_mode(),
        users=[AdminUserOut.model_validate(user) for user in users.all()],
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(user_id: int, body: AdminUserUpdate, db: DB) -> AppUser:
    user = await db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    if body.status is not None:
        user.status = body.status
        if body.status == "DISABLED":
            await revoke_sessions(db, user.id)
    if body.role is not None:
        user.role = body.role
    if body.verify_email and user.email_verified_at is None:
        user.email_verified_at = utcnow()
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(db: DB, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[InviteOut]:
    now = utcnow()
    rows = await db.scalars(select(InviteCode).order_by(InviteCode.id.desc()).limit(limit))
    return [InviteOut.from_invite(row, now) for row in rows.all()]


@router.post("/invites", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite(body: InviteCreate, db: DB) -> InviteOut:
    now = utcnow()
    for _ in range(3):
        invite = InviteCode(
            code=new_invite_code(),
            note=body.note.strip(),
            max_uses=body.max_uses,
            used_count=0,
            expires_at=now + timedelta(days=body.expires_in_days) if body.expires_in_days else None,
        )
        db.add(invite)
        try:
            await db.commit()
        except IntegrityError:  # 32^12 olasilikta cakisma; yeni kodla dene
            await db.rollback()
            continue
        await db.refresh(invite)
        return InviteOut.from_invite(invite, now)
    raise HTTPException(status_code=500, detail="Davet kodu üretilemedi")


@router.delete("/invites/{invite_id}", response_model=InviteOut)
async def revoke_invite(invite_id: int, db: DB) -> InviteOut:
    invite = await db.get(InviteCode, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Davet kodu bulunamadı")
    now = utcnow()
    if invite.revoked_at is None:
        invite.revoked_at = now
        await db.commit()
        await db.refresh(invite)
    return InviteOut.from_invite(invite, now)
