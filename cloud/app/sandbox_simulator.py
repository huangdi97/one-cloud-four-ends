"""HCP 沙箱仿真子路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from cloud.app.services.rep_workbench.hcp_sandbox_service import HcpSandboxService
from shared.auth_scope import require_scope
from shared.base import success

simulator_router = APIRouter()


class SimulateRequest(BaseModel):
    scenario: str
    strategy: str = ""


@simulator_router.post("/profiles/{hcp_id}/simulate")
def simulate(
    hcp_id: int,
    body: SimulateRequest,
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    user_id = int(current_user["sub"])
    row = service.simulate(
        hcp_id=hcp_id,
        scenario=body.scenario,
        strategy=body.strategy,
        user_id=user_id,
    )
    return success(data=row)


@simulator_router.get("/simulations")
def list_simulations(
    hcp_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    result = service.list_simulations(
        hcp_id=hcp_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@simulator_router.get("/simulations/{sim_id}")
def get_simulation(
    sim_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    row = service.get_simulation(sim_id)
    return success(data=row)


@simulator_router.get("/dashboard")
def dashboard(
    current_user: dict = Depends(require_scope("visit")),
    service: HcpSandboxService = Depends(),
):
    result = service.dashboard()
    return success(data=result)
