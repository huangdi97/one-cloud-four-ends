"""Agent 协作路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.collab.collaboration_service import CollaborationService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/collaboration", tags=["Agent Collaboration"])


class SkillRegister(BaseModel):
    skill_name: str
    agent_role: str
    description: str = ""
    entity_types: list[str] = []
    capabilities: list[str] = []
    confidence: float = 0.5
    priority: int = 100


class SessionCreate(BaseModel):
    task_description: str
    source_entity_id: str = ""
    source_agent_role: str = ""
    orchestrator_agent: str = ""
    routing_strategy: str = "semantic"


class StepAdd(BaseModel):
    agent_role: str
    action_type: str = "process"
    input_summary: str = ""
    entity_id: str = ""


class StepComplete(BaseModel):
    output_summary: str = ""
    status: str = "completed"
    duration_seconds: int = 0


class RouteRequest(BaseModel):
    task_description: str
    entity_type: str = ""
    entity_id: str = ""
    routing_strategy: str = "semantic"


@router.post(
    "/skills/register",
    status_code=status.HTTP_201_CREATED,
    summary="注册Agent技能",
    description="注册一个新的Agent技能到协作系统",
    tags=["Agent Collaboration"],
)
def register_skill(
    body: SkillRegister,
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """注册 Agent 技能。"""
    row = service.register_skill(
        skill_name=body.skill_name,
        agent_role=body.agent_role,
        description=body.description,
        entity_types=body.entity_types,
        capabilities=body.capabilities,
        confidence=body.confidence,
        priority=body.priority,
    )
    return success(data=row)


@router.get("/skills/list", summary="列出已注册技能", description="根据Agent角色等条件列出已注册的技能列表", tags=["Agent Collaboration"])
def list_skills(
    agent_role: Optional[str] = Query(None),
    enabled: Optional[int] = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """列出已注册的技能。"""
    rows = service.list_skills(agent_role=agent_role, enabled=enabled)
    return success(data=rows)


@router.delete("/skills/{skill_id}", summary="删除指定技能", description="根据技能ID删除已注册的技能", tags=["Agent Collaboration"])
def delete_skill(
    skill_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """删除指定技能。"""
    service.delete_skill(skill_id)
    return success(data={"deleted": skill_id})


@router.post(
    "/sessions/create",
    status_code=status.HTTP_201_CREATED,
    summary="创建协作会话",
    description="创建一个新的Agent协作会话",
    tags=["Agent Collaboration"],
)
def create_session(
    body: SessionCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """创建协作会话。"""
    row = service.create_session(
        task_description=body.task_description,
        source_entity_id=body.source_entity_id,
        source_agent_role=body.source_agent_role,
        orchestrator_agent=body.orchestrator_agent,
        routing_strategy=body.routing_strategy,
    )
    return success(data=row)


@router.post(
    "/sessions/{session_id}/step",
    status_code=status.HTTP_201_CREATED,
    summary="添加会话步骤",
    description="向指定协作会话添加一个处理步骤",
    tags=["Agent Collaboration"],
)
def add_session_step(
    session_id: str,
    body: StepAdd,
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """向会话添加步骤。"""
    row = service.add_session_step(
        session_id=session_id,
        agent_role=body.agent_role,
        action_type=body.action_type,
        input_summary=body.input_summary,
        entity_id=body.entity_id,
    )
    return success(data=row)


@router.post(
    "/sessions/{session_id}/step/{step_id}/complete",
    summary="完成指定步骤",
    description="标记协作会话中的指定步骤为已完成",
    tags=["Agent Collaboration"],
)
def complete_step(
    session_id: str,
    step_id: int,
    body: StepComplete,
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """完成指定步骤。"""
    result = service.complete_step(
        session_id=session_id,
        step_id=step_id,
        output_summary=body.output_summary,
        status_val=body.status,
        duration_seconds=body.duration_seconds,
    )
    return success(data=result)


@router.get("/sessions/list", summary="分页列出协作会话", description="根据状态等条件分页列出协作会话列表", tags=["Agent Collaboration"])
def list_sessions(
    status: Optional[str] = Query(None),
    source_agent_role: Optional[str] = Query(None),
    routing_strategy: Optional[str] = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """分页列出协作会话。"""
    rows = service.list_sessions(
        status=status,
        source_agent_role=source_agent_role,
        routing_strategy=routing_strategy,
    )
    return success(data=rows)


@router.get("/sessions/{session_id}", summary="获取会话详情", description="根据会话ID获取协作会话的详细信息", tags=["Agent Collaboration"])
def get_session(
    session_id: str,
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """获取会话详情。"""
    result = service.get_session(session_id)
    return success(data=result)


@router.post("/route", summary="语义路由任务", description="将任务描述通过语义路由分配合适的Agent处理", tags=["Agent Collaboration"])
def semantic_route(
    body: RouteRequest,
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """语义路由任务到合适的 Agent。"""
    result = service.semantic_route(
        task_description=body.task_description,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        routing_strategy=body.routing_strategy,
    )
    return success(data=result)


@router.get("/dashboard", summary="获取协作仪表盘数据", description="获取Agent协作系统的仪表盘统计数据", tags=["Agent Collaboration"])
def dashboard(
    current_user: dict = Depends(require_scope("visit")),
    service: CollaborationService = Depends(),
):
    """获取协作仪表盘数据。"""
    result = service.dashboard()
    return success(data=result)
