"""整改工单路由 — 红灯事件的后续管理 API。"""

import logging

from fastapi import APIRouter, HTTPException

from cloud.app.services.compliance_svc.remediation_scoring import ScoreService
from cloud.app.services.compliance_svc.remediation_service import RemediationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/remediation", tags=["remediation"])

_REMEDIATION_DB = "data/remediation.db"
_service = RemediationService(_REMEDIATION_DB)
_score_service = ScoreService(_service)


@router.get("/orders")
def list_orders(status: str | None = None):
    """列出整改工单，可选按状态过滤。"""
    return {"orders": _service.list_orders(status)}


@router.post("/orders", status_code=201)
def create_order(red_flag_id: str, assigned_to: str = ""):
    """手动创建整改工单。"""
    order = _service.create_from_red_flag(red_flag_id, assigned_to)
    if "error" in order:
        raise HTTPException(status_code=400, detail=order["error"])
    return order


@router.get("/orders/{order_id}")
def get_order(order_id: str):
    """获取单个工单。"""
    order = _service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@router.patch("/orders/{order_id}")
def update_order(order_id: str, notes: str | None = None, assigned_to: str | None = None):
    """更新工单（备注、责任人）。"""
    order = _service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")

    conn = _service._get_db()
    updates = []
    params = []
    if notes is not None:
        updates.append("notes=?")
        params.append(notes)
    if assigned_to is not None:
        updates.append("assigned_to=?")
        params.append(assigned_to)
    if updates:
        params.append(order_id)
        conn.execute(
            f"UPDATE remediation_orders SET {', '.join(updates)} WHERE order_id=?",
            params,
        )
        conn.commit()
    conn.close()
    return _service.get_order(order_id)


@router.post("/orders/{order_id}/transition")
def transition_order(order_id: str, target_status: str, operator: str = "system"):
    """状态转换。"""
    result = _service.transition(order_id, target_status, operator)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/orders/{order_id}/score")
def score_order(order_id: str, score: int, notes: str = "", evidence_checked: bool = False):
    """复查评分。分数1-4返回需要审阅的对象，5通过归档。"""
    result = _score_service.score_order(order_id, score, notes, evidence_checked)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result
