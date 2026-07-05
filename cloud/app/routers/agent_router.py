"""Combined agent router — aggregates agent execution and orchestration endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.agent_ops.agent_execution_service import AgentExecutionService
from cloud.app.services.platform_svc.orchestrate_service import OrchestrateService
from shared.auth_scope import require_scope
from shared.base import success

# ── Agent Execution (prefix /agent/exec) ──────────────────────────────

exec_router = APIRouter(prefix="/agent/exec", tags=["Agent系统"])


class TaskSubmit(BaseModel):
    agent_role: str = ""
    action_type: str = "process"
    input_data: dict = {}
    max_retries: int = 3


class A2ATask(BaseModel):
    task_id: str = ""
    agent_role: str = ""
    input_data: dict = {}
    callback_url: str = ""


@exec_router.post("/submit", status_code=status.HTTP_201_CREATED, tags=["Agent系统"])
def submit_task(body: TaskSubmit, current_user=Depends(require_scope("visit"))):
    svc = AgentExecutionService()
    return success(data=svc.submit_task(body, current_user))


@exec_router.get("/tasks/list", tags=["Agent系统"])
def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    agent_role: Optional[str] = Query(None),
    current_user=Depends(require_scope("visit")),
):
    svc = AgentExecutionService()
    return success(data=svc.list_tasks(status_filter, agent_role))


@exec_router.get("/tasks/{task_id}", tags=["Agent系统"])
def get_task(task_id: str, current_user=Depends(require_scope("visit"))):
    svc = AgentExecutionService()
    return success(data=svc.get_task(task_id))


@exec_router.post("/tasks/{task_id}/retry", tags=["Agent系统"])
def retry_task(task_id: str, current_user=Depends(require_scope("visit"))):
    svc = AgentExecutionService()
    return success(data=svc.retry_task(task_id))


@exec_router.post("/tasks/{task_id}/approve", tags=["Agent系统"])
def approve_task(task_id: str, current_user=Depends(require_scope("visit"))):
    svc = AgentExecutionService()
    return success(data=svc.approve_task(task_id))


@exec_router.get("/a2a/card", tags=["Agent系统"])
def a2a_card(current_user=Depends(require_scope("visit"))):
    svc = AgentExecutionService()
    return success(data=svc.a2a_card())


@exec_router.post("/a2a/task", status_code=status.HTTP_201_CREATED, tags=["Agent系统"])
def a2a_task(body: A2ATask, current_user=Depends(require_scope("visit"))):
    svc = AgentExecutionService()
    return success(data=svc.a2a_task(body))


# ── Orchestrate (prefix /orchestrate) ─────────────────────────────────

orch_router = APIRouter(prefix="/orchestrate", tags=["Orchestration"])


class TemplateCreate(BaseModel):
    template_name: str
    description: str = ""
    steps: list[dict] = []


class OrchestrateRun(BaseModel):
    template_name: str
    context: dict = {}


@orch_router.post("/templates/create", status_code=status.HTTP_201_CREATED, tags=["Orchestration"])
def create_template(
    body: TemplateCreate,
    current_user=Depends(require_scope("visit")),
    service: OrchestrateService = Depends(),
):
    uid = int(current_user["sub"])
    row = service.create_template(
        template_name=body.template_name,
        description=body.description,
        steps=body.steps,
        user_id=uid,
    )
    return success(data=row)


@orch_router.get("/templates/list", tags=["Orchestration"])
def list_templates(
    enabled: Optional[int] = Query(None),
    current_user=Depends(require_scope("visit")),
    service: OrchestrateService = Depends(),
):
    rows = service.list_templates(enabled=enabled)
    return success(data=rows)


@orch_router.post("/run", status_code=status.HTTP_201_CREATED, tags=["Orchestration"])
def run_orchestration(
    body: OrchestrateRun,
    current_user=Depends(require_scope("visit")),
    service: OrchestrateService = Depends(),
):
    result = service.run_orchestration(
        template_name=body.template_name,
        context=body.context,
    )
    return success(data=result)


# ── Main aggregator ───────────────────────────────────────────────────

router = APIRouter()
router.include_router(exec_router)
router.include_router(orch_router)
