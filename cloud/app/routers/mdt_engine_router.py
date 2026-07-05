"""MDT 会诊引擎路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from cloud.app.services.collab.mdt_engine_service import MdtEngineService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/mdt", tags=["MDT会诊"])


class ParticipantDef(BaseModel):
    agent_role_id: int
    role_name: str
    stance: str = "neutral"
    vote_weight: float = 1.0


class SessionCreate(BaseModel):
    title: str
    question: str
    context: str = ""
    participants: list[ParticipantDef] = []


class DebateRequest(BaseModel):
    max_rounds: int = 1


# --- endpoints ---


@router.post("/sessions", status_code=201, tags=["MDT会诊"])
def create_session(
    body: SessionCreate,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MdtEngineService = Depends(),
):
    """创建新的 MDT 会诊会话。"""
    uid = int(current_user["sub"])
    return success(data=service.create_session(body, uid))


@router.get("/sessions", tags=["MDT会诊"])
def list_sessions(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_scope("visit")),
    service: MdtEngineService = Depends(),
):
    """分页查询会诊会话列表。"""
    return success(data=service.list_sessions(status_filter, page, page_size))


@router.get("/sessions/{session_id}", tags=["MDT会诊"])
def get_session(
    session_id: int,
    current_user=Depends(require_scope("visit")),
    service: MdtEngineService = Depends(),
):
    """获取会诊会话详情，含参与者和意见。"""
    return success(data=service.get_session(session_id))


@router.post("/sessions/{session_id}/debate", tags=["MDT会诊"])
def debate(
    session_id: int,
    body: DebateRequest,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MdtEngineService = Depends(),
):
    """在会话中执行多轮 Multi-Disciplinary 辩论。"""
    auth = request.headers.get("Authorization", "")
    return success(data=service.debate(session_id, body.max_rounds, auth))


@router.post("/sessions/{session_id}/consensus", tags=["MDT会诊"])
def consensus(
    session_id: int,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MdtEngineService = Depends(),
):
    """基于各方辩论意见生成综合共识报告。"""
    auth = request.headers.get("Authorization", "")
    return success(data=service.consensus(session_id, auth))


@router.get("/sessions/{session_id}/opinions", tags=["MDT会诊"])
def get_opinions(
    session_id: int,
    round_number: Optional[int] = Query(None),
    current_user=Depends(require_scope("visit")),
    service: MdtEngineService = Depends(),
):
    """获取会诊会话中的意见列表。"""
    return success(data=service.get_opinions(session_id, round_number))


@router.get("/sessions/{session_id}/timeline", tags=["MDT会诊"])
def timeline(
    session_id: int,
    current_user=Depends(require_scope("visit")),
    service: MdtEngineService = Depends(),
):
    """获取会诊的时间线视图，按轮次组织。"""
    return success(data=service.timeline(session_id))


@router.get("/dashboard", tags=["MDT会诊"])
def dashboard(
    current_user=Depends(require_scope("visit")),
    service: MdtEngineService = Depends(),
):
    """获取 MDT 会诊仪表盘统计。"""
    return success(data=service.dashboard())
