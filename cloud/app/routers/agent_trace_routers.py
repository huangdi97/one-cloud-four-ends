"""Agent Trace 路由聚合 — 注册 trace / context / failure 三个子路由。"""

from fastapi import APIRouter

from cloud.app.services.agent_ops.agent_trace_service import trace_context_router, trace_failure_router, trace_router

router = APIRouter()
router.include_router(trace_router)
router.include_router(trace_context_router)
router.include_router(trace_failure_router)
