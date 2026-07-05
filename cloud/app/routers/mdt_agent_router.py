"""MDT 会诊 Agent 分配路由。"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from cloud.app.services.collab.mdt_agent_service import MdtAgentService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/mdt", tags=["MDT会诊"])


class AssignmentItem(BaseModel):
    """AssignmentItem 服务类。"""

    agent_instance_key: str
    task_content: str
    priority: int = 3


class BatchAssignBody(BaseModel):
    """BatchAssignBody 服务类。"""

    assignments: list[AssignmentItem]


@router.get("/sessions/{session_id}/agents", summary="List all Framework Agents", tags=["MDT会诊"])
def list_framework_agents(
    session_id: int,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MdtAgentService = Depends(),
):
    """list_framework_agents 操作。

    Args:
        session_id: 描述
        current_user: 描述
        service: 描述
    """
    participants = service.get_framework_participants(session_id)
    return success(participants)


@router.post("/sessions/{session_id}/assign", status_code=201, summary="Assign Tasks", tags=["MDT会诊"])
def assign_tasks(
    session_id: int,
    body: BatchAssignBody,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MdtAgentService = Depends(),
):
    """assign_tasks 操作。

    Args:
        session_id: 描述
        current_user: 描述
        service: 描述
    """
    assignments = [a.model_dump() for a in body.assignments]
    results = service.batch_assign(session_id, assignments)
    return success({"assignments": results})


@router.get("/sessions/{session_id}/tasks", summary="List all Session Tasks", tags=["MDT会诊"])
def list_session_tasks(
    session_id: int,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MdtAgentService = Depends(),
):
    """list_session_tasks 操作。

    Args:
        session_id: 描述
        current_user: 描述
        service: 描述
    """
    tasks = service.list_session_tasks(session_id)
    return success(tasks)
