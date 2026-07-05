"""飞检准备度仪表盘 API。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.compliance_svc.capa_workflow_service import confirm_remediation
from cloud.app.services.platform_svc.flying_inspection_crud import (
    create_remediation_task,
    get_audit_trail,
    get_checklist,
    get_dashboard,
    get_history,
)
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/inspection", tags=["飞检准备度"])


class RemediationTaskCreate(BaseModel):
    title: str
    description: str = ""
    assignee: str
    deadline: str
    inspection_id: str = "inspection-2026-06"
    who: str = "质量负责人"
    evidence: str = "remediation-task-form"


class RemediationConfirm(BaseModel):
    inspection_id: str = "inspection-2026-06"
    who: str = "质量负责人"
    evidence: str = "remediation-evidence"


@router.get("/dashboard", tags=["飞检准备度"])
def inspection_dashboard(_: dict = Depends(require_scope("visit"))):
    return success(data=get_dashboard())


@router.get("/checklist", tags=["飞检准备度"])
def inspection_checklist(category: Optional[str] = Query(None, description="检查类别"), _: dict = Depends(require_scope("visit"))):
    return success(data=get_checklist(category=category))


@router.post("/task", status_code=status.HTTP_201_CREATED, tags=["飞检准备度"])
def inspection_task_create(body: RemediationTaskCreate, _: dict = Depends(require_scope("visit"))):
    return success(
        data=create_remediation_task(
            title=body.title,
            description=body.description,
            assignee=body.assignee,
            deadline=body.deadline,
            inspection_id=body.inspection_id,
            who=body.who,
            evidence=body.evidence,
        )
    )


@router.put("/task/{task_id}/confirm", tags=["飞检准备度"])
def inspection_task_confirm(task_id: str, body: RemediationConfirm | None = None, _: dict = Depends(require_scope("visit"))):
    request = body or RemediationConfirm()
    return success(
        data=confirm_remediation(
            task_id,
            inspection_id=request.inspection_id,
            who=request.who,
            evidence=request.evidence,
        )
    )


@router.get("/history", tags=["飞检准备度"])
def inspection_history(_: dict = Depends(require_scope("visit"))):
    return success(data=get_history())


@router.get("/{inspection_id}/audit-trail", tags=["飞检准备度"])
def inspection_audit_trail(inspection_id: str, _: dict = Depends(require_scope("visit"))):
    return success(data=get_audit_trail(inspection_id))
