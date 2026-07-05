from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from cloud.app.decision_analyst import DecisionAnalyst
from cloud.app.services.compliance_svc.decision_intel_service import DecisionIntelService
from shared.auth_scope import require_scope

analysis_router = APIRouter()

_analyst = DecisionAnalyst()


class CaseCreate(BaseModel):
    name: str
    pipeline_run_id: Optional[int] = None
    description: str = ""
    outcome: str = ""
    outcome_score: float = 0.0
    context: dict = {}
    tags: list = []


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    outcome: Optional[str] = None
    outcome_score: Optional[float] = None
    context: Optional[dict] = None
    tags: Optional[list] = None


class AnalyzeRequest(BaseModel):
    custom_question: str = ""


class ReflectRequest(BaseModel):
    filter_tags: list = []
    max_cases: int = 10


@analysis_router.post("/cases", status_code=201)
def create_case(
    body: CaseCreate,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.create_case(body, request, current_user, service)


@analysis_router.get("/cases")
def list_cases(
    outcome_score_min: Optional[float] = Query(None),
    outcome_score_max: Optional[float] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.list_cases(
        outcome_score_min=outcome_score_min,
        outcome_score_max=outcome_score_max,
        tag=tag,
        search=search,
        page=page,
        page_size=page_size,
        current_user=current_user,
        service=service,
    )


@analysis_router.get("/cases/{case_id}")
def get_case(
    case_id: int,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.get_case(case_id, current_user, service)


@analysis_router.patch("/cases/{case_id}")
def update_case(
    case_id: int,
    body: CaseUpdate,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.update_case(case_id, body, current_user, service)


@analysis_router.delete("/cases/{case_id}")
def delete_case(
    case_id: int,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.delete_case(case_id, current_user, service)


@analysis_router.post("/cases/{case_id}/analyze")
def analyze_case(
    case_id: int,
    body: AnalyzeRequest,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.analyze_case(case_id, body, request, current_user, service)


@analysis_router.get("/cases/{case_id}/analyses")
def list_analyses(
    case_id: int,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.list_analyses(case_id, current_user, service)


@analysis_router.get("/analyses/{analysis_id}")
def get_analysis(
    analysis_id: int,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.get_analysis(analysis_id, current_user, service)


@analysis_router.post("/reflect")
def reflect(
    body: ReflectRequest,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: DecisionIntelService = Depends(),
):
    return _analyst.reflect(body, request, current_user, service)
