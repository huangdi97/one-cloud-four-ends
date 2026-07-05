"""联邦学习节点路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette import status

from cloud.app.services.brain.federated_node_service import FederatedNodeService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/federated", tags=["联邦学习"])


class RegisterNodeBody(BaseModel):
    """RegisterNodeBody 服务类。"""

    node_id: str
    node_name: str = ""
    node_type: str = "partner"
    organization: str = ""
    endpoint_url: str = ""
    public_key: str = ""
    data_summary: str = "{}"


class HeartbeatBody(BaseModel):
    """HeartbeatBody 服务类。"""

    data_summary: Optional[str] = None


class UpdateStatusBody(BaseModel):
    """UpdateStatusBody 服务类。"""

    status: str
    reliability_score: Optional[float] = None


@router.post(
    "/nodes/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register Node",
    description="向联邦学习网络注册一个新的节点，包含节点标识、类型、组织和公钥等信息。",
    tags=["联邦学习"],
)
def register_node(
    body: RegisterNodeBody,
    _=Depends(require_scope(["pharma", "research"])),
    service: FederatedNodeService = Depends(),
):
    """register_node 操作。

    Args:
        _: 描述
        service: 描述
    """
    row = service.register_node(
        node_id=body.node_id,
        node_name=body.node_name,
        node_type=body.node_type,
        organization=body.organization,
        endpoint_url=body.endpoint_url,
        public_key=body.public_key,
        data_summary=body.data_summary,
    )
    return success(data=row)


@router.get("/nodes", summary="List all Nodes", description="查询联邦学习节点列表，可按状态和节点类型进行筛选。", tags=["联邦学习"])
def list_nodes(
    status: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),
    _=Depends(require_scope(["pharma", "research"])),
    service: FederatedNodeService = Depends(),
):
    """list_nodes 操作。

    Args:
        status: 描述
        node_type: 描述
        _: 描述
        service: 描述
    """
    rows = service.list_nodes(status_filter=status, node_type=node_type)
    return success(data=rows)


@router.get("/nodes/{node_id}", summary="Get Node by ID", description="根据节点 ID 获取联邦学习节点的详细信息。", tags=["联邦学习"])
def get_node(
    node_id: str,
    _=Depends(require_scope(["pharma", "research"])),
    service: FederatedNodeService = Depends(),
):
    """get_node 操作。

    Args:
        node_id: 描述
        _: 描述
        service: 描述
    """
    row = service.get_node(node_id)
    return success(data=row)


@router.post("/nodes/{node_id}/heartbeat", summary="Node Heartbeat", description="发送节点心跳，更新节点在线状态和数据摘要信息。", tags=["联邦学习"])
def node_heartbeat(
    node_id: str,
    body: HeartbeatBody,
    _=Depends(require_scope(["pharma", "research"])),
    service: FederatedNodeService = Depends(),
):
    """node_heartbeat 操作。

    Args:
        node_id: 描述
        _: 描述
        service: 描述
    """
    row = service.heartbeat(node_id=node_id, data_summary=body.data_summary)
    return success(data=row)


@router.get("/dashboard", summary="Get dashboard data", description="获取联邦学习仪表盘数据，支持按天筛选和 CSV 导出。", tags=["联邦学习"])
def dashboard(
    days: Optional[int] = Query(None, description="Filter data within recent N days"),
    export: Optional[bool] = Query(False, description="Export as CSV"),
    _=Depends(require_scope(["pharma", "research"])),
    service: FederatedNodeService = Depends(),
):
    """dashboard 操作。

    Args:
        days: 描述
        export: 描述
        _: 描述
        service: 描述
    """
    if export:
        csv_content = service.export_dashboard_csv(days=days)
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=dashboard-audit.csv"},
        )
    data = service.get_dashboard(days=days)
    return success(data=data)


@router.get("/audit-log", summary="Audit Log", description="获取联邦学习审计日志，支持按天筛选和 CSV 导出。", tags=["联邦学习"])
def audit_log(
    days: Optional[int] = Query(None, description="Filter within recent N days"),
    export: Optional[bool] = Query(False, description="Export as CSV"),
    _=Depends(require_scope(["pharma", "research"])),
    service: FederatedNodeService = Depends(),
):
    """audit_log 操作。

    Args:
        days: 描述
        export: 描述
        _: 描述
        service: 描述
    """
    if export:
        csv_content = service.export_audit_log_csv(days=days)
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
        )
    data = service.get_audit_log(days=days)
    return success(data=data)


@router.get(
    "/compliance-summary", summary="Compliance Summary", description="获取联邦学习节点合规性汇总数据，包括合规评分和审计结果。", tags=["联邦学习"]
)
def compliance_summary(
    _=Depends(require_scope(["pharma", "research"])),
    service: FederatedNodeService = Depends(),
):
    """compliance_summary 操作。

    Args:
        _: 描述
        service: 描述
    """
    data = service.get_compliance_summary()
    return success(data=data)
