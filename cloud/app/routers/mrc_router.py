from fastapi import APIRouter, Depends

from cloud.app.schemas.mrc_workflow import (
    ComplianceApproveRequest,
    DistributionRequest,
    MaterialCreate,
    MRCDecisionRequest,
)
from cloud.app.services.intel.mrc_workflow_service import (
    approve,
    create_material,
    distribute,
    mrc_decision,
    submit_compliance,
    submit_mrc,
    track,
)
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/mrc", tags=["MRC审核流"])


@router.post("/material", status_code=201, summary="创建营销材料", tags=["MRC审核流"])
def create_mrc_material(body: MaterialCreate, _: dict = Depends(require_scope("visit"))):
    return success(data=create_material(body))


@router.put("/material/{id}/submit-mrc", summary="提交 MRC 审核", tags=["MRC审核流"])
def submit_material_to_mrc(id: str, _: dict = Depends(require_scope("visit"))):
    return success(data=submit_mrc(id))


@router.put("/material/{id}/mrc-decision", summary="MRC 审核决策", tags=["MRC审核流"])
def decide_mrc_material(id: str, body: MRCDecisionRequest, _: dict = Depends(require_scope("visit"))):
    return success(data=mrc_decision(id, body))


@router.put("/material/{id}/compliance-approve", summary="合规审批", tags=["MRC审核流"])
def approve_material_compliance(id: str, body: ComplianceApproveRequest, _: dict = Depends(require_scope("visit"))):
    submit_compliance(id)
    return success(data=approve(id, body))


@router.post("/material/{id}/distribute", summary="分发营销材料", tags=["MRC审核流"])
def distribute_material(id: str, body: DistributionRequest, _: dict = Depends(require_scope("visit"))):
    return success(data=distribute(id, body))


@router.get("/material/{id}/effectiveness", summary="查看材料效果", tags=["MRC审核流"])
def get_material_effectiveness(id: str, _: dict = Depends(require_scope("visit"))):
    return success(data=track(id))
