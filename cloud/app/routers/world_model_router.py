"""世界模型路由 — 认知发现API。"""

import logging

from fastapi import APIRouter, Query

from cloud.app.services.brain.world_model_service import WorldModelService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/world-model", tags=["world-model"])

_service = WorldModelService()


@router.get("/cognitions")
def list_cognitions(
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    agent_key: str | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    """获取认知发现列表。支持按置信度和Agent过滤。"""
    cognitions = _service.get_cognitions(min_confidence, agent_key, limit)
    return {"cognitions": [c.to_dict() for c in cognitions], "total": len(cognitions)}


@router.post("/scan")
def trigger_scan():
    """手动触发全量扫描。"""
    results = _service.full_scan()
    return {"status": "completed", "count": len(results)}
