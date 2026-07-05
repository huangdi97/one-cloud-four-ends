"""系统配置管理路由。"""

from typing import Any, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cloud.app.services.platform_svc.config_service import ConfigService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/admin/configs", tags=["配置"])


class ConfigItem(BaseModel):
    key: str
    value: str
    description: str = ""


@router.get("/", tags=["配置"])
def list_configs(
    current_user: dict = Depends(require_scope("visit")),
    service: ConfigService = Depends(),
) -> Any:
    """列出所有配置项。"""
    rows = service.list_configs()
    return success(data=rows)


@router.put("/", tags=["配置"])
def batch_upsert_configs(
    body: List[ConfigItem],
    current_user: dict = Depends(require_scope("visit")),
    service: ConfigService = Depends(),
) -> Any:
    """批量更新或插入配置项。"""
    user_id = int(current_user["sub"])
    rows = service.batch_upsert_configs(body, user_id)
    return success(data=rows)


@router.get("/{key}", tags=["配置"])
def get_config(
    key: str,
    current_user: dict = Depends(require_scope("visit")),
    service: ConfigService = Depends(),
) -> Any:
    """获取指定配置项。"""
    return success(data=service.get_config(key))
