"""Gemini/N8N gibi hassas calisma-zamani ayarlarinin yonetimi.

Degerler Redis'te tutulur (bkz. app/core/dynamic_settings.py); container
yeniden baslatilmadan degistirilip denenebilir. Deger asla API yanitinda
tam olarak dondurulmez, yalnizca maskelenmis onizleme.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.routers.schedules import require_admin_token
from app.core.dynamic_settings import clear_setting, get_setting_statuses, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


@router.get("")
async def list_settings() -> list[dict]:
    return await get_setting_statuses()


@router.put("/{key}")
async def update_setting(
    key: str, payload: SettingUpdate, _admin: Annotated[str, Depends(require_admin_token)]
) -> dict:
    try:
        await set_setting(key, payload.value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/{key}")
async def delete_setting(key: str, _admin: Annotated[str, Depends(require_admin_token)]) -> dict:
    try:
        await clear_setting(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
