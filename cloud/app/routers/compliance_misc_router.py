"""合并的合规杂项路由：审计日志、全息记忆、信任审计、窜货检测。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from starlette import status

from cloud.app.database import get_db
from cloud.app.services.compliance_svc.audit_service import AuditService
from cloud.app.services.compliance_svc.diversion_service import DiversionDetectionService
from cloud.app.services.compliance_svc.holographic_service import HolographicService
from cloud.app.services.compliance_svc.trust_audit_service import TrustAuditService
from shared.auth_scope import require_scope
from shared.base import success

# ── audit_router ───────────────────────────────────────────────────────

audit_router = APIRouter(prefix="/audit", tags=["审计日志"])


class AuditLogCreate(BaseModel):
    user_id: int
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    detail: str = ""
    source_end: str = "cloud"
    ip_address: str = ""


@audit_router.post("/logs", status_code=status.HTTP_201_CREATED, tags=["审计日志"])
def create_audit_log(
    body: AuditLogCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: AuditService = Depends(),
) -> Any:
    service.create_log(
        user_id=body.user_id,
        action=body.action,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        detail=body.detail,
        source_end=body.source_end,
        ip_address=body.ip_address,
    )
    return success(message="audit log recorded")


@audit_router.get("/logs", tags=["审计日志"])
def list_audit_logs(
    entity_type: str = Query(None),
    entity_id: int = Query(None),
    action: str = Query(None),
    user_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: AuditService = Depends(),
) -> Any:
    result = service.list_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@audit_router.get("/logs/stats", tags=["审计日志"])
def audit_stats(
    current_user: dict = Depends(require_scope("visit")),
    service: AuditService = Depends(),
) -> Any:
    return success(data=service.get_stats())


# ── holographic_router ────────────────────────────────────────────────

holographic_router = APIRouter(prefix="/memory", tags=["记忆系统"])


class AssociateRequest(BaseModel):
    memory_id_b: int
    relation_type: str = "related"
    weight: float = 1.0


@holographic_router.post("/{memory_id}/associate", status_code=status.HTTP_201_CREATED, tags=["记忆系统"])
def create_association(
    memory_id: int,
    body: AssociateRequest,
    request: Request,
    current_user=Depends(require_scope("visit")),
    db=Depends(get_db),
):
    service = HolographicService(db)
    result = service.create_association(
        memory_id_a=memory_id,
        memory_id_b=body.memory_id_b,
        relation_type=body.relation_type,
        weight=body.weight,
    )
    return success(data=result)


@holographic_router.get("/{memory_id}/holographic", tags=["记忆系统"])
def holographic_get(
    memory_id: int,
    depth: int = 3,
    db=Depends(get_db),
):
    service = HolographicService(db)
    result = service.holographic_graph(memory_id, depth)
    return success(data=result)


@holographic_router.get("/{memory_id}/associations", tags=["记忆系统"])
def get_associations(
    memory_id: int,
    limit: int = 50,
    db=Depends(get_db),
):
    service = HolographicService(db)
    result = service.get_associations(memory_id, limit)
    return success(data=result)


@holographic_router.delete("/associations/{association_id}", tags=["记忆系统"])
def delete_association(
    association_id: int,
    request: Request,
    current_user=Depends(require_scope("visit")),
    db=Depends(get_db),
):
    service = HolographicService(db)
    result = service.delete_association(association_id)
    return success(data=result)


# ── trust_audit_router ────────────────────────────────────────────────

trust_audit_router = APIRouter(prefix="/api/trust-audit", tags=["信任审计"])


class CreateBlockRequest(BaseModel):
    data: dict = {}
    block_type: str = "audit"
    node_id: str = ""
    created_by: str = ""


@trust_audit_router.get("/score/{node_id}", summary="Get Trust Score by ID", description="根据节点ID计算信任评分", tags=["信任审计"])
def get_trust_score(
    node_id: str,
    _: dict = Depends(require_scope("visit")),
    service: TrustAuditService = Depends(),
):
    result = service.calculate_trust_score(node_id)
    return success(data=result)


@trust_audit_router.post("/blocks", status_code=201, summary="Create Block", description="创建新的审计区块", tags=["信任审计"])
def create_block(
    body: CreateBlockRequest,
    _: dict = Depends(require_scope("visit")),
    service: TrustAuditService = Depends(),
):
    result = service.create_audit_block(
        data=body.data,
        block_type=body.block_type,
        node_id=body.node_id,
        created_by=body.created_by,
    )
    return success(data=result)


@trust_audit_router.get("/verify", summary="Verify Chain", description="验证信任审计链的完整性", tags=["信任审计"])
def verify_chain(
    _: dict = Depends(require_scope("visit")),
    service: TrustAuditService = Depends(),
):
    result = service.verify_chain()
    return success(data=result)


@trust_audit_router.get("/blocks", summary="List all Blocks", description="分页查询审计区块列表，可按节点ID过滤", tags=["信任审计"])
def list_blocks(
    node_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _: dict = Depends(require_scope("visit")),
    service: TrustAuditService = Depends(),
):
    result = service.get_chain(node_id=node_id or "", limit=limit)
    return success(data=result)


# ── diversion_router ──────────────────────────────────────────────────

diversion_router = APIRouter(prefix="/diversion", tags=["窜货检测"])


class CheckDistributionRequest(BaseModel):
    product: str
    region: str
    quantity: int = 0
    dealer_id: str = ""
    rep_id: str = ""


class BatchCheckRequest(BaseModel):
    distributions: list[CheckDistributionRequest]


@diversion_router.post("/check", summary="检测窜货", description="检测产品流向是否存在窜货风险")
def check_distribution(
    body: CheckDistributionRequest,
    db=Depends(get_db),
):
    service = DiversionDetectionService(db)
    return success(data=service.check_distribution(body.model_dump()))


@diversion_router.post("/run-batch", summary="批量检测窜货", description="批量检测多笔产品流向，每笔均经全息稽核引擎验证")
def run_batch(
    body: BatchCheckRequest,
    db=Depends(get_db),
):
    service = DiversionDetectionService(db)
    results = []
    for dist in body.distributions:
        check_result = service.check_distribution(dist.model_dump())
        holographic_result = service.run_holographic_audit_check(dist.model_dump())
        results.append(
            {
                "product": dist.product,
                "region": dist.region,
                "check": check_result,
                "holographic_result": holographic_result,
            }
        )
    return success(data=results)


@diversion_router.get("/records/{rep_id}", summary="查询窜货记录", description="查询代表在指定天数内的窜货记录")
def get_records(
    rep_id: str,
    days: int = Query(30, ge=1, le=365),
    db=Depends(get_db),
):
    service = DiversionDetectionService(db)
    return success(data=service.get_diversion_records(rep_id, days))


# ── top-level aggregator router ───────────────────────────────────────

router = APIRouter()
router.include_router(audit_router)
router.include_router(holographic_router)
router.include_router(trust_audit_router)
router.include_router(diversion_router)

__all__ = [
    "router",
    "audit_router",
    "holographic_router",
    "trust_audit_router",
    "diversion_router",
    "AssociateRequest",
    "AuditLogCreate",
    "BatchCheckRequest",
    "CheckDistributionRequest",
    "CreateBlockRequest",
]
