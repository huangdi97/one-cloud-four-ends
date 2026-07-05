"""决策情报报告子路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from cloud.app.intel_reporter import IntelReporter
from cloud.app.services.compliance_svc.decision_intel_service import DecisionIntelService
from shared.auth_scope import require_scope

reporting_router = APIRouter()

_reporter = IntelReporter()


class InsightUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    confidence: Optional[float] = None
    applicability: Optional[str] = None


@reporting_router.get("/insights")
def list_insights(
    insight_type: Optional[str] = Query(None),
    confidence_min: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _reporter.list_insights(
        insight_type=insight_type,
        confidence_min=confidence_min,
        page=page,
        page_size=page_size,
        current_user=current_user,
        service=service,
    )


@reporting_router.get("/insights/{insight_id}")
def get_insight(
    insight_id: int,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _reporter.get_insight(insight_id, current_user, service)


@reporting_router.patch("/insights/{insight_id}")
def update_insight(
    insight_id: int,
    body: InsightUpdate,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _reporter.update_insight(insight_id, body, current_user, service)


@reporting_router.get("/dashboard")
def dashboard(
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _reporter.dashboard(current_user, service)
