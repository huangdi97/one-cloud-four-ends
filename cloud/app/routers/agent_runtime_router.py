"""Agent 运行时执行路由。"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from cloud.app.agent_database import get_agent_db
from cloud.app.agent_runtime.audit.agent_audit import AgentAuditor
from cloud.app.agent_runtime.tools.tool_bridge import ToolBridge
from cloud.app.services.agent_ops.agent_runtime_service import AgentRuntimeService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/agent/runtime", tags=["Agent Runtime"])


class ExecuteRequest(BaseModel):
    agent_key: str
    goal: str
    context: dict | None = None


class TriggerRequest(BaseModel):
    goal: str | None = None


class RollbackRequest(BaseModel):
    step: int


def _auth_header(request: Request) -> str:
    return request.headers.get("Authorization", "")


@router.post("/execute", tags=["Agent Runtime"])
def execute(
    body: ExecuteRequest,
    request: Request,
    user=Depends(require_scope("visit")),
):
    service = AgentRuntimeService()
    return service.execute_agent(body.goal, body.agent_key, body.context, _auth_header(request))


@router.get("/status", tags=["Agent Runtime"])
def get_status(
    user=Depends(require_scope("visit")),
):
    return AgentRuntimeService().get_status()


@router.get("/logs", tags=["Agent Runtime"])
def get_logs(
    agent_key: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(require_scope("visit")),
):
    return AgentRuntimeService().get_logs(agent_key, status, page, page_size)


@router.post("/trigger/{agent_key}", tags=["Agent Runtime"])
def trigger_agent(
    agent_key: str,
    request: Request,
    body: TriggerRequest = TriggerRequest(),
    user=Depends(require_scope("visit")),
):
    service = AgentRuntimeService()
    return service.trigger_agent(agent_key, body.goal, _auth_header(request))


@router.get("/tools", tags=["Agent Runtime"])
def list_tools(
    user=Depends(require_scope("visit")),
):
    registry = ToolBridge()
    registry.register_default_tools()
    return registry.list_tools()


@router.get("/approvals/pending", tags=["Agent Runtime"])
def list_pending_approvals(
    user=Depends(require_scope("visit")),
):
    return success(data={"items": AgentRuntimeService().list_pending_approvals()})


@router.post("/approvals/{approval_id}/approve", tags=["Agent Runtime"])
def approve_approval(
    approval_id: int,
    user=Depends(require_scope("visit")),
):
    username = user.get("username", "unknown")
    AgentRuntimeService().approve_approval(approval_id, username)
    return success(message="approved", data={"approval_id": approval_id})


@router.post("/approvals/{approval_id}/reject", tags=["Agent Runtime"])
def reject_approval(
    approval_id: int,
    user=Depends(require_scope("visit")),
):
    username = user.get("username", "unknown")
    AgentRuntimeService().reject_approval(approval_id, username)
    return success(message="rejected", data={"approval_id": approval_id})


@router.post("/resume", tags=["Agent Runtime"])
def resume_execution(
    request: Request,
    user=Depends(require_scope("visit")),
):
    """恢复一个等待审批的 Agent 执行。"""
    service = AgentRuntimeService()
    return service.resume_execution(_auth_header(request))


@router.post("/rollback/{trace_id}", tags=["Agent Runtime"])
def rollback_execution(
    trace_id: str,
    body: RollbackRequest,
    request: Request,
    user=Depends(require_scope("visit")),
):
    service = AgentRuntimeService()
    return service.rollback_execution(trace_id, body.step, _auth_header(request))


# ── Audit (prefix /agent/runtime/audit) ────────────────────────────────


@router.post("/audit/log", tags=["Agent Runtime"])
def audit_log_interaction(
    user_id: str = Query(...),
    agent_key: str = Query(...),
    user_action: str = Query(...),
    task_type: str = Query(""),
    confidence: float = Query(0.0),
    feedback: str = Query(""),
    user=Depends(require_scope("visit")),
    db=Depends(get_agent_db),
):
    auditor = AgentAuditor(db)
    auditor.log_interaction(
        user_id=user_id,
        agent_key=agent_key,
        user_action=user_action,
        task_type=task_type,
        confidence=confidence,
        feedback=feedback,
    )
    return success(message="logged")


@router.get("/audit/logs", tags=["Agent Runtime"])
def audit_query_logs(
    user_id: str = Query(""),
    agent_key: str = Query(""),
    user_action: str = Query(""),
    start: str = Query(""),
    end: str = Query(""),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user=Depends(require_scope("visit")),
    db=Depends(get_agent_db),
):
    auditor = AgentAuditor(db)
    return success(data=auditor.query_logs(user_id, agent_key, user_action, start, end, limit, offset))


@router.get("/audit/report", tags=["Agent Runtime"])
def audit_report(
    days: int = Query(7, ge=1, le=90),
    user=Depends(require_scope("visit")),
    db=Depends(get_agent_db),
):
    auditor = AgentAuditor(db)
    return success(data=auditor.get_summary_report(days))


@router.get("/audit/trends", tags=["Agent Runtime"])
def audit_trends(
    days: int = Query(7, ge=1, le=90),
    user=Depends(require_scope("visit")),
    db=Depends(get_agent_db),
):
    auditor = AgentAuditor(db)
    return success(data=auditor.get_feedback_trends(days))


@router.get("/audit/dismissed", tags=["Agent Runtime"])
def audit_high_dismiss(
    days: int = Query(7, ge=1, le=90),
    min_count: int = Query(3, ge=1),
    user=Depends(require_scope("visit")),
    db=Depends(get_agent_db),
):
    auditor = AgentAuditor(db)
    return success(data=auditor.get_high_dismiss(days, min_count))
