"""Gemini/N8N gibi hassas calisma-zamani ayarlarinin yonetimi.

Degerler Redis'te tutulur (bkz. app/core/dynamic_settings.py); container
yeniden baslatilmadan degistirilip denenebilir. Deger asla API yanitinda
tam olarak dondurulmez, yalnizca maskelenmis onizleme.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.routers.schedules import require_admin_token
from app.core.dynamic_settings import (
    clear_setting,
    get_setting_statuses,
    resolve_settings,
    set_setting,
)
from app.llm.diagnostics import GeminiDiagnosticResult, test_gemini_connection

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


class GeminiTestRequest(BaseModel):
    tier: Literal[1, 2]


@router.get("")
async def list_settings() -> list[dict]:
    return await get_setting_statuses()


@router.post("/gemini/test", response_model=GeminiDiagnosticResult)
async def test_gemini(
    payload: GeminiTestRequest,
    _admin: Annotated[str, Depends(require_admin_token)],
) -> GeminiDiagnosticResult:
    active_settings = await resolve_settings()
    try:
        return await test_gemini_connection(active_settings, tier=payload.tier)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        message = str(exc).replace(active_settings.gemini_api_key, "***")
        raise HTTPException(
            status_code=502,
            detail=f"Gemini baglanti testi basarisiz: {message[:300]}",
        ) from exc


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
