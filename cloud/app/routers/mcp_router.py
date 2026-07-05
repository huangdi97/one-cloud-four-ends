"""MCP 工具管理路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.brain.mcp_tool_service import McpToolService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/mcp", tags=["MCP"])


class ToolRegister(BaseModel):
    tool_name: str
    description: str = ""
    endpoint_url: str = ""
    input_schema: dict = {}
    output_schema: dict = {}


@router.post("/tools/register", status_code=status.HTTP_201_CREATED, tags=["MCP"])
def register_tool(body: ToolRegister, current_user=Depends(require_scope("visit"))):
    """注册一个新的 MCP 工具。

    Args:
        body: 工具信息（名称、描述、端点、输入/输出 schema）。

    Returns:
        注册后的工具记录。
    """
    uid = int(current_user["sub"])
    role = current_user.get("role", "rep")
    return success(data=McpToolService().register_tool(body, uid, role))


@router.get("/tools/list", tags=["MCP"])
def list_tools(
    enabled: Optional[int] = Query(None),
    current_user=Depends(require_scope("visit")),
):
    """获取已注册的工具列表。

    Args:
        enabled: 按启用状态筛选。

    Returns:
        工具列表。
    """
    role = current_user.get("role", "rep")
    return success(data=McpToolService().list_tools(enabled, role))


@router.patch("/tools/{tool_id}/toggle", tags=["MCP"])
def toggle_tool(tool_id: int, current_user=Depends(require_scope("visit"))):
    """切换工具的启用/禁用状态。

    Args:
        tool_id: 工具 ID。

    Returns:
        更新后的工具信息。
    """
    role = current_user.get("role", "rep")
    return success(data=McpToolService().toggle_tool(tool_id, role))


@router.delete("/tools/{tool_id}", status_code=status.HTTP_200_OK, tags=["MCP"])
def delete_tool(tool_id: int, current_user=Depends(require_scope("visit"))):
    """删除指定工具。

    Args:
        tool_id: 要删除的工具 ID。

    Returns:
        被删除的工具 ID。
    """
    role = current_user.get("role", "rep")
    return success(data=McpToolService().delete_tool(tool_id, role))
