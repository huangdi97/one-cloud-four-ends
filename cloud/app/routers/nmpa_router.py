"""NMPA 合规检查路由。

路由前缀：/compliance/gov
核心数据模型：NmpaCheck 与 NMPA 合规检查日志。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from cloud.app.services.intel.nmpa_service import NmpaService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/compliance/gov", tags=["NMPA Compliance"])


class NmpaCheck(BaseModel):
    document_type: str
    content: str


@router.post("/check", tags=["NMPA Compliance"])
def nmpa_check(
    body: NmpaCheck,
    user: dict = Depends(require_scope("visit")),
    service: NmpaService = Depends(),
):
    """提交文档进行 NMPA 合规检查。
    Args: body 请求体. Returns: 检查结果.
    """
    user_id = int(user["sub"])
    result = service.check(body.document_type, body.content, user_id)
    return success(result)


@router.get("/logs/list", tags=["NMPA Compliance"])
def logs_list(
    document_type: Optional[str] = Query(None),
    check_result: Optional[str] = Query(None),
    human_review_required: Optional[int] = Query(None),
    user: dict = Depends(require_scope("visit")),
    service: NmpaService = Depends(),
):
    """查询 NMPA 检查日志。
    Args: 按文档类型/检查结果/人工审核筛选. Returns: 日志列表.
    """
    result = service.list_logs(
        document_type=document_type,
        check_result=check_result,
        human_review_required=human_review_required,
    )
    return success(result)
