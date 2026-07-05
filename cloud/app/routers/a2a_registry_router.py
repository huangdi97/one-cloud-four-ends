"""Agent-to-Agent 注册与心跳路由。"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.agent_ops.a2a_registry_service import A2aRegistryService
from shared.auth_scope import require_scope
from shared.base import success


class RegisterRequest(BaseModel):
    """RegisterRequest 服务类。"""

    agent_key: str
    agent_name: str = ""
    agent_type: str = "generic"
    description: str = ""
    capabilities: list[str] = []
    endpoint_url: str = ""


class HeartbeatRequest(BaseModel):
    """HeartbeatRequest 服务类。"""

    agent_key: str


class StatusUpdateRequest(BaseModel):
    """StatusUpdateRequest 服务类。"""

    agent_key: str
    status: str


class TaskSubmitRequest(BaseModel):
    """TaskSubmitRequest 服务类。"""

    source_agent_key: str = ""
    target_agent_key: str = ""
    task_type: str = "generic"
    input_data: dict = {}
    priority: int = 3


router = APIRouter(prefix="/a2a", tags=["A2A Agent Registry"])


@router.post(
    "/agents/register",
    status_code=status.HTTP_201_CREATED,
    summary="注册Agent",
    description="向注册中心注册新的Agent实例",
    tags=["A2A Agent Registry"],
)
def register_agent(
    body: RegisterRequest,
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """register_agent 操作。

    Args:
        service: 描述
        _: 描述
    """
    data = service.register_agent(
        body.agent_key,
        body.agent_name,
        body.agent_type,
        body.description,
        body.capabilities,
        body.endpoint_url,
    )
    return success(data=data)


@router.get("/agents/{agent_key}", summary="查询Agent", description="根据agent_key获取Agent详情", tags=["A2A Agent Registry"])
def get_agent(
    agent_key: str,
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """get_agent 操作。

    Args:
        agent_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.get_agent(agent_key))


@router.get("/agents", summary="Agent列表", description="按类型/状态/能力筛选Agent列表", tags=["A2A Agent Registry"])
def list_agents(
    type: str = Query(None, alias="type"),
    status: str = Query(None),
    capability: str = Query(None),
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """list_agents 操作。

    Args:
        type: 描述
        status: 描述
        capability: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.list_agents(agent_type=type, status=status, capability=capability))


@router.post("/agents/{agent_key}/heartbeat", summary="Agent心跳", description="发送Agent心跳更新最后活跃时间", tags=["A2A Agent Registry"])
def agent_heartbeat(
    agent_key: str,
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """agent_heartbeat 操作。

    Args:
        agent_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.heartbeat(agent_key))


@router.patch("/agents/{agent_key}/status", summary="更新状态", description="更新Agent的运行状态", tags=["A2A Agent Registry"])
def update_agent_status(
    agent_key: str,
    body: StatusUpdateRequest,
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """update_agent_status 操作。

    Args:
        agent_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.update_status(agent_key, body.status))


@router.post(
    "/tasks/submit", status_code=status.HTTP_201_CREATED, summary="提交任务", description="向目标Agent提交一个任务", tags=["A2A Agent Registry"]
)
def submit_task(
    body: TaskSubmitRequest,
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """submit_task 操作。

    Args:
        service: 描述
        _: 描述
    """
    data = service.submit_task(
        body.source_agent_key,
        body.target_agent_key,
        body.task_type,
        body.input_data,
        body.priority,
    )
    return success(data=data)


@router.get("/tasks/{task_id}", summary="查询任务", description="根据task_id获取任务详情", tags=["A2A Agent Registry"])
def get_task(
    task_id: str,
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """获取任务。

    Args:
        task_id: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.get_task(task_id))


@router.get("/tasks", summary="任务列表", description="按状态和Agent筛选任务列表", tags=["A2A Agent Registry"])
def list_tasks(
    status: str = Query(None),
    agent_key: str = Query(None),
    limit: int = Query(50),
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """获取任务列表。

    Args:
        status: 描述
        agent_key: 描述
        limit: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.list_tasks(status=status, agent_key=agent_key, limit=limit))


@router.get("/events", summary="事件列表", description="按类型和Agent筛选事件列表", tags=["A2A Agent Registry"])
def list_events(
    event_type: str = Query(None),
    agent_key: str = Query(None),
    limit: int = Query(50),
    service: A2aRegistryService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """list_events 操作。

    Args:
        event_type: 描述
        agent_key: 描述
        limit: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.list_events(event_type=event_type, agent_key=agent_key, limit=limit))
