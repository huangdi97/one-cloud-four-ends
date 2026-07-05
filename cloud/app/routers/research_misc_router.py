"""合并的科研杂项路由：审计、路线、合规执行、导出。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from starlette import status
from starlette.responses import Response

from cloud.app.compliance.research_enforcer import ResearchComplianceEnforcer
from cloud.app.services.brain.route_tsp import (
    estimate_travel_time,
    haversine,
    optimize_route,
)
from cloud.app.services.intel.research_audit_service import (
    get_audit_log,
    get_audit_logs,
    get_audit_logs_by_type,
    record_switch,
)
from cloud.app.services.intel.research_export_service import export_pi_csv, export_quotation
from cloud.app.services.intel.research_service import ResearchService
from shared.auth import get_current_user
from shared.auth_scope import require_scope
from shared.base import success

# ── research_audit_router ──────────────────────────────────────────────

audit_router = APIRouter(
    prefix="/api/research/audit",
    tags=["科研线"],
    dependencies=[Depends(require_scope("research"))],
)


class SwitchRequest(BaseModel):
    from_mode: str
    to_mode: str
    device_id: str = ""
    gps: str = ""


@audit_router.get("/logs", summary="审计日志列表", description="分页查询科研审计日志", tags=["Research Audit"])
def list_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    logs = get_audit_logs(page=page, per_page=per_page)
    return {"code": 0, "data": logs, "message": "success"}


@audit_router.get("/logs/{log_id}", summary="审计日志详情", description="根据ID查询单条审计日志的详细信息", tags=["Research Audit"])
def get_log(
    log_id: int,
    current_user: dict = Depends(get_current_user),
):
    log = get_audit_log(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")
    return {"code": 0, "data": log, "message": "success"}


@audit_router.get("/logs/by-type/{event_type}", summary="按类型查询审计日志", description="根据事件类型过滤审计日志", tags=["Research Audit"])
def list_logs_by_type(
    event_type: str,
    current_user: dict = Depends(get_current_user),
):
    logs = get_audit_logs_by_type(event_type)
    return {"code": 0, "data": logs, "message": "success"}


@audit_router.post("/switch", status_code=201, summary="记录模式切换", description="记录科研模式之间的切换操作", tags=["Research Audit"])
def switch_mode(
    body: SwitchRequest,
    current_user: dict = Depends(get_current_user),
):
    operator = current_user.get("username", "")
    record_switch(
        from_mode=body.from_mode,
        to_mode=body.to_mode,
        operator=operator,
        device_id=body.device_id,
        gps=body.gps,
    )
    return success(message="switch logged")


# ── research_route_router ─────────────────────────────────────────────

route_router = APIRouter(
    prefix="/api/research/route",
    tags=["research-route"],
    dependencies=[Depends(require_scope("research"))],
)


class PointItem(BaseModel):
    pi_id: int
    name: str
    lat: float
    lng: float
    priority: str = "normal"


class OptimizeRequest(BaseModel):
    points: list[PointItem]


class EstimateRequest(BaseModel):
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float


@route_router.post("/optimize", summary="路线优化", description="对多个科研路线点进行路径优化排序", tags=["Research"])
def post_optimize(
    body: OptimizeRequest,
    current_user: dict = Depends(get_current_user),
):
    points = [p.model_dump() for p in body.points]
    result = optimize_route(points)
    return {"code": 0, "data": result, "message": "success"}


@route_router.post("/estimate", summary="距离时间估算", description="估算两点之间的直线距离和预计行程时间", tags=["Research"])
def post_estimate(
    body: EstimateRequest,
    current_user: dict = Depends(get_current_user),
):
    distance = haversine(body.from_lat, body.from_lng, body.to_lat, body.to_lng)
    time_est = estimate_travel_time(distance)
    return success(
        data={
            "distance_km": round(distance, 2),
            "travel_time_hours": time_est,
        }
    )


# ── research_enforcer_router ──────────────────────────────────────────

enforcer_router = APIRouter(
    prefix="/api/research/compliance",
    tags=["科研线"],
    dependencies=[Depends(require_scope("research"))],
)


class ResearchVisitCheckRequest(BaseModel):
    visit_data: dict


def _serialize_violations(violations):
    return [
        {
            "rule_code": v.rule_code,
            "rule_name": v.rule_name,
            "severity": v.severity,
            "action": v.action,
            "detail": v.detail,
        }
        for v in violations
    ]


def enforce_research_visit(
    body: ResearchVisitCheckRequest,
    current_user: dict = Depends(get_current_user),
):
    db = ResearchService().get_research_db()
    try:
        enforcer = ResearchComplianceEnforcer(db)
        violations = enforcer.check_research_visit(body.visit_data)
        return success(
            data={
                "violations": _serialize_violations(violations),
                "passed": len(violations) == 0,
            }
        )
    finally:
        db.close()


@enforcer_router.get("/enforce/rules", tags=["Research Enforcer"])
def list_research_rules(
    current_user: dict = Depends(get_current_user),
):
    db = ResearchService().get_research_db()
    try:
        enforcer = ResearchComplianceEnforcer(db)
        return success(data={"rules": enforcer.get_l1_rules()})
    finally:
        db.close()


# ── research_export_router ────────────────────────────────────────────

export_router = APIRouter(
    prefix="/api/research/export",
    tags=["科研线"],
    dependencies=[Depends(require_scope("research"))],
)


@export_router.get("/pi", tags=["Research Export"])
def export_pi(
    format: str = Query("csv", description="Export format"),
    current_user: dict = Depends(get_current_user),
):
    if format != "csv":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV format supported")
    content = export_pi_csv()
    ResearchService().log_audit(
        event_type="export",
        entity_type="pi",
        entity_id=0,
        new_value="export_format=csv",
        operator=current_user.get("username", ""),
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pi_export.csv"},
    )


@export_router.get("/quotation/{quotation_id}", tags=["Research Export"])
def export_quotation_endpoint(
    quotation_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = export_quotation(quotation_id)
        ResearchService().log_audit(
            event_type="export",
            entity_type="quotation",
            entity_id=quotation_id,
            new_value="export_format=json",
            operator=current_user.get("username", ""),
        )
        return {"code": 0, "data": data, "message": "success"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── top-level aggregator router ───────────────────────────────────────

router = APIRouter()
router.include_router(audit_router)
router.include_router(route_router)
router.include_router(enforcer_router)
router.include_router(export_router)

__all__ = [
    "router",
    "audit_router",
    "enforcer_router",
    "export_router",
    "route_router",
    "EstimateRequest",
    "OptimizeRequest",
    "PointItem",
    "ResearchVisitCheckRequest",
    "SwitchRequest",
]
