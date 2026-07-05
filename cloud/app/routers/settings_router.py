"""管理员设置路由。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cloud.app.services.rep_workbench.settings_service import SettingsService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/admin/settings", tags=["配置"])


class SettingsBody(BaseModel):
    settings: dict


@router.get("", tags=["配置"])
def get_all(user: dict = Depends(require_scope("visit"))):
    service = SettingsService()
    result = service.get_all()
    return success(data=result)


@router.put("", tags=["配置"])
def update(body: SettingsBody, user: dict = Depends(require_scope("visit"))):
    service = SettingsService()
    for key, value in body.settings.items():
        service.set(key, value)
    result = service.get_all()
    return success(data=result)
