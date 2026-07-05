"""合规执行器路由：拜访合规检查与规则列表。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cloud.app.services.compliance_svc.enforcer_service import EnforcerService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/compliance/enforce", tags=["合规"])


class VisitCheckRequest(BaseModel):
    """拜访检查请求体。"""

    visit_data: dict


@router.post("", summary="拜访合规检查", description="对拜访数据进行合规检查", tags=["合规"])
def enforce_visit(
    body: VisitCheckRequest,
    _: dict = Depends(require_scope("visit")),
    service: EnforcerService = Depends(),
):
    return success(data=service.check_visit(body.visit_data))


@router.get("/rules", summary="规则列表", description="获取所有合规规则列表", tags=["合规"])
def list_rules(
    _: dict = Depends(require_scope("visit")),
    service: EnforcerService = Depends(),
):
    return success(data=service.list_rules())
