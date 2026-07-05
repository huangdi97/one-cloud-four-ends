"""细胞网络路由：Agent 细胞注册、发现、路由同步等 API。"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services import CellNetworkService
from cloud.app.services.platform_svc.cell_topology_service import CellTopologyService
from shared.auth import get_current_user
from shared.auth_scope import require_scope
from shared.base import success


class RegisterCellRequest(BaseModel):
    """RegisterCellRequest 服务类。"""

    agent_instance_key: str


class RouteTaskRequest(BaseModel):
    """RouteTaskRequest 服务类。"""

    source_key: str
    target_key: str
    task_data: dict = {}


router = APIRouter(prefix="/cell-network", tags=["细胞网络"])


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="注册细胞", description="注册一个新的Agent细胞到网络中", tags=["细胞网络"])
def register_cell(
    body: RegisterCellRequest,
    service: CellNetworkService = Depends(),
    current_user: dict = Depends(get_current_user),
    _=Depends(require_scope(["pharma", "research"])),
):
    """register_cell 操作。

    Args:
        service: 描述
        current_user: 描述
        _: 描述
    """
    return success(data=service.register_cell(body.agent_instance_key))


@router.get("/discover", summary="发现细胞", description="根据能力查询可用的Agent细胞", tags=["细胞网络"])
def discover_cells(
    capability: str | None = Query(None),
    service: CellNetworkService = Depends(),
    current_user: dict = Depends(get_current_user),
    _=Depends(require_scope(["pharma", "research"])),
):
    """discover_cells 操作。

    Args:
        capability: 描述
        service: 描述
        current_user: 描述
        _: 描述
    """
    return success(data=service.discover_cells(capability=capability))


@router.post("/route", summary="路由任务", description="将任务路由到目标Agent细胞", tags=["细胞网络"])
def route_to_cell(
    body: RouteTaskRequest,
    service: CellNetworkService = Depends(),
    current_user: dict = Depends(get_current_user),
    _=Depends(require_scope(["pharma", "research"])),
):
    """route_to_cell 操作。

    Args:
        service: 描述
        current_user: 描述
        _: 描述
    """
    return success(data=service.route_to_cell(body.source_key, body.target_key, body.task_data))


@router.post("/sync/{cell_key}", summary="同步路由表", description="同步指定细胞的路由表信息", tags=["细胞网络"])
def sync_routing_table(
    cell_key: str,
    service: CellNetworkService = Depends(),
    current_user: dict = Depends(get_current_user),
    _=Depends(require_scope(["pharma", "research"])),
):
    """sync_routing_table 操作。

    Args:
        cell_key: 描述
        service: 描述
        current_user: 描述
        _: 描述
    """
    return success(data=service.sync_routing_table(cell_key))


@router.get("/topology", summary="获取网络拓扑", description="获取当前细胞网络的拓扑结构", tags=["细胞网络"])
def get_network_topology(
    service: CellNetworkService = Depends(),
    current_user: dict = Depends(get_current_user),
    _=Depends(require_scope(["pharma", "research"])),
):
    """get_network_topology 操作。

    Args:
        service: 描述
        current_user: 描述
        _: 描述
    """
    return success(data=service.get_network_topology())


@router.get("/topology/analyze", summary="分析拓扑", description="分析细胞网络拓扑结构并返回分析结果", tags=["细胞网络"])
def analyze_topology(
    service: CellTopologyService = Depends(),
    current_user: dict = Depends(get_current_user),
    _=Depends(require_scope(["pharma", "research"])),
):
    """analyze_topology 操作。

    Args:
        service: 描述
        current_user: 描述
        _: 描述
    """
    return success(data=service.analyze_topology())


@router.get("/topology/suggest", summary="建议优化", description="基于拓扑分析给出网络优化建议", tags=["细胞网络"])
def suggest_optimization(
    service: CellTopologyService = Depends(),
    current_user: dict = Depends(get_current_user),
    _=Depends(require_scope(["pharma", "research"])),
):
    """suggest_optimization 操作。

    Args:
        service: 描述
        current_user: 描述
        _: 描述
    """
    return success(data=service.suggest_optimization())
