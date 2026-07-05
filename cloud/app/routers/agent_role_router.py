"""Agent 角色管理路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.agent_ops.agent_role_service import AgentRoleService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/agent/roles", tags=["Agent系统"])


class RoleCreate(BaseModel):
    name: str
    role_type: str = "sales_rep"
    description: str = ""
    system_prompt: str
    input_schema: str = "{}"
    output_schema: str = "{}"
    temperature: float = 0.7
    max_tokens: int = 2048
    allowed_tools: str = "[]"


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    role_type: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    input_schema: Optional[str] = None
    output_schema: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    allowed_tools: Optional[str] = None
    is_active: Optional[int] = None


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建角色", description="创建Agent角色并返回角色数据", tags=["Agent系统"])
def create_role(
    body: RoleCreate,
    current_user=Depends(require_scope("visit")),
    service: AgentRoleService = Depends(),
):
    """创建Agent角色并返回角色数据。"""
    uid = int(current_user["sub"])
    return success(data=service.create_role(body, uid))


@router.get("", summary="角色列表", description="按类型和状态筛选Agent角色列表", tags=["Agent系统"])
def list_roles(
    role_type: Optional[str] = Query(None),
    is_active: Optional[int] = Query(None),
    current_user=Depends(require_scope("visit")),
    service: AgentRoleService = Depends(),
):
    """按类型和状态筛选Agent角色列表。"""
    return success(data=service.list_roles(role_type=role_type, is_active=is_active))


@router.get("/{role_id}", summary="查询角色", description="获取指定角色的详细信息", tags=["Agent系统"])
def get_role(
    role_id: int,
    current_user=Depends(require_scope("visit")),
    service: AgentRoleService = Depends(),
):
    """获取指定角色的详细信息。"""
    return success(data=service.get_role(role_id))


@router.patch("/{role_id}", summary="更新角色", description="部分更新Agent角色字段", tags=["Agent系统"])
def update_role(
    role_id: int,
    body: RoleUpdate,
    current_user=Depends(require_scope("visit")),
    service: AgentRoleService = Depends(),
):
    """部分更新Agent角色字段。"""
    return success(data=service.update_role(role_id, body))


@router.delete("/{role_id}", summary="删除角色", description="软删除指定Agent角色", tags=["Agent系统"])
def delete_role(
    role_id: int,
    current_user=Depends(require_scope("visit")),
    service: AgentRoleService = Depends(),
):
    """软删除指定Agent角色。"""
    service.delete_role(role_id)
    return success()
