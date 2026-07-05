"""SOAP 决策路由与端点。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from cloud.app.services.rep_workbench.soap_decision_service import SoapDecisionService
from cloud.app.soap_templater import create_template, list_templates
from cloud.app.soap_validator import DecisionCreate, DecisionUpdate, FinalizeRequest, OpinionCreate
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/soap", tags=["SOAP Decision"])

router.post("/templates", status_code=201)(create_template)
router.get("/templates")(list_templates)


@router.post("/decisions", status_code=201, tags=["SOAP Decision"])
def create_decision(
    body: DecisionCreate,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(
        service.create_decision(
            title=body.title,
            template_id=body.template_id,
            subjective=body.subjective,
            objective=body.objective,
            assessment=body.assessment,
            plan=body.plan,
            priority=body.priority,
            tags=body.tags,
            created_by=cu["user_id"],
        )
    )


@router.get("/decisions", tags=["SOAP Decision"])
def list_decisions(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(data=service.list_decisions(status=status, priority=priority, tag=tag, page=page, page_size=page_size))


@router.get("/decisions/{decision_id}", tags=["SOAP Decision"])
def get_decision(
    decision_id: int,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(service.get_decision(decision_id))


@router.patch("/decisions/{decision_id}", tags=["SOAP Decision"])
def update_decision(
    decision_id: int,
    body: DecisionUpdate,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(
        service.update_decision(
            decision_id=decision_id,
            subjective=body.subjective,
            objective=body.objective,
            assessment=body.assessment,
            plan=body.plan,
            priority=body.priority,
            tags=body.tags,
        )
    )


@router.post("/decisions/{decision_id}/submit", tags=["SOAP Decision"])
def submit_decision(
    decision_id: int,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(service.submit_decision(decision_id))


@router.post("/decisions/{decision_id}/opinions", tags=["SOAP Decision"])
def add_opinion(
    decision_id: int,
    body: OpinionCreate,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(
        service.add_opinion(
            decision_id=decision_id,
            opinion=body.opinion,
            stance=body.stance,
            supporting_data=body.supporting_data,
            confidence=body.confidence,
            attachments=body.attachments,
            user_id=cu["user_id"],
            role=cu.get("role", ""),
        )
    )


@router.get("/decisions/{decision_id}/opinions", tags=["SOAP Decision"])
def list_opinions(
    decision_id: int,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(service.list_opinions(decision_id))


@router.post("/decisions/{decision_id}/finalize", tags=["SOAP Decision"])
def finalize_decision(
    decision_id: int,
    body: FinalizeRequest,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(
        service.finalize_decision(
            decision_id=decision_id,
            decision_summary=body.decision_summary,
            user_id=cu["user_id"],
        )
    )


@router.get("/dashboard", tags=["SOAP Decision"])
def dashboard(cu=Depends(require_scope("visit")), service: SoapDecisionService = Depends()):
    return success(service.dashboard())
