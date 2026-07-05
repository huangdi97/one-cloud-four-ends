"""HCP 沙箱管理子路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.rep_workbench.hcp_sandbox_service import HcpSandboxService
from shared.auth_scope import require_scope
from shared.base import success

manager_router = APIRouter()


class HcpCreate(BaseModel):
    name: str
    title: str = ""
    hospital: str = ""
    department: str = ""
    specialty: str = ""
    city: str = ""
    tier: str = "B"
    traits: dict = {}
    prescription_volume: float = 0
    influence_score: float = 0.5
    digital_engagement: float = 0.5


class HcpUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    hospital: Optional[str] = None
    department: Optional[str] = None
    specialty: Optional[str] = None
    city: Optional[str] = None
    tier: Optional[str] = None
    traits: Optional[dict] = None
    prescription_volume: Optional[float] = None
    influence_score: Optional[float] = None
    digital_engagement: Optional[float] = None
    is_active: Optional[int] = None


class InteractionCreate(BaseModel):
    interaction_type: str
    content: str = ""
    response: str = ""
    outcome: str = ""
    strategy_used: str = ""
    conducted_at: Optional[str] = None


@manager_router.post("/profiles", status_code=status.HTTP_201_CREATED)
def create_profile(
    body: HcpCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    user_id = int(current_user["sub"])
    row = service.create_profile(
        name=body.name,
        title=body.title,
        hospital=body.hospital,
        department=body.department,
        specialty=body.specialty,
        city=body.city,
        tier=body.tier,
        traits=body.traits,
        prescription_volume=body.prescription_volume,
        influence_score=body.influence_score,
        digital_engagement=body.digital_engagement,
        user_id=user_id,
    )
    return success(data=row)


@manager_router.get("/profiles")
def list_profiles(
    tier: Optional[str] = Query(None),
    specialty: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    result = service.list_profiles(
        tier=tier,
        specialty=specialty,
        city=city,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@manager_router.get("/profiles/{hcp_id}")
def get_profile(
    hcp_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    row = service.get_profile(hcp_id)
    return success(data=row)


@manager_router.patch("/profiles/{hcp_id}")
def update_profile(
    hcp_id: int,
    body: HcpUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    row = service.update_profile(
        hcp_id=hcp_id,
        name=body.name,
        title=body.title,
        hospital=body.hospital,
        department=body.department,
        specialty=body.specialty,
        city=body.city,
        tier=body.tier,
        traits=body.traits,
        prescription_volume=body.prescription_volume,
        influence_score=body.influence_score,
        digital_engagement=body.digital_engagement,
        is_active=body.is_active,
    )
    return success(data=row)


@manager_router.post("/profiles/{hcp_id}/interactions")
def create_interaction(
    hcp_id: int,
    body: InteractionCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    user_id = int(current_user["sub"])
    row = service.create_interaction(
        hcp_id=hcp_id,
        interaction_type=body.interaction_type,
        content=body.content,
        response=body.response,
        outcome=body.outcome,
        strategy_used=body.strategy_used,
        conducted_at=body.conducted_at,
        user_id=user_id,
    )
    return success(data=row)


@manager_router.get("/profiles/{hcp_id}/interactions")
def list_interactions(
    hcp_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    result = service.list_interactions(
        hcp_id=hcp_id,
        page=page,
        page_size=page_size,
    )
    return success(data=result)
