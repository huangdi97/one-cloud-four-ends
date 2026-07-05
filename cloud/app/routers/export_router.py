"""数据导出路由。"""

from typing import Any

from fastapi import APIRouter, Depends

from cloud.app.services.platform_svc.export_service import ExportService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/export", tags=["数据导出"])


@router.get("/audit-logs", summary="导出审计日志", description="导出审计日志数据，用于离线分析和存档。", tags=["数据导出"])
def export_audit_logs(
    current_user: dict = Depends(require_scope("visit")),
    service: ExportService = Depends(),
) -> Any:
    """导出审计日志数据。

    Args:
        current_user: 当前认证用户。
        service: 导出服务实例。

    Returns:
        包含审计日志导出数据的响应。
    """
    return success(data=service.export_audit_logs())


@router.get("/customers", summary="导出客户数据", description="导出客户数据，用于外部系统分析或备份。", tags=["数据导出"])
def export_customers(
    current_user: dict = Depends(require_scope("visit")),
    service: ExportService = Depends(),
) -> Any:
    """导出客户数据。

    Args:
        current_user: 当前认证用户。
        service: 导出服务实例。

    Returns:
        包含客户导出数据的响应。
    """
    return success(data=service.export_customers())
