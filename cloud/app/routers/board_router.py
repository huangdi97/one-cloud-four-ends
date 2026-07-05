"""看板管理路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette import status

from cloud.app.services.platform_svc.board_service import BoardService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/boards", tags=["团队管理"])


class BoardCreate(BaseModel):
    name: str
    description: str = ""


class BoardUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.post("/", status_code=status.HTTP_201_CREATED, summary="创建看板", description="创建一个新的团队看板", tags=["团队管理"])
def create_board(
    body: BoardCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: BoardService = Depends(),
) -> Any:
    """创建团队面板。Args: body (BoardCreate) 面板创建体; current_user (dict) 用户; service (BoardService) 面板服务。Returns: Any 成功响应"""
    user_id = int(current_user["sub"])
    result = service.create_board(name=body.name, description=body.description, owner_id=user_id)
    return success(data=result)


@router.get("/", summary="看板列表", description="获取所有团队看板列表", tags=["团队管理"])
def list_boards(
    current_user: dict = Depends(require_scope("visit")),
    service: BoardService = Depends(),
) -> Any:
    """获取所有面板列表。Args: current_user (dict) 用户; service (BoardService) 面板服务。Returns: Any 成功响应"""
    return success(data=service.list_boards())


@router.get("/{board_id}", summary="查询看板", description="获取指定看板详情", tags=["团队管理"])
def get_board(
    board_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: BoardService = Depends(),
) -> Any:
    """获取指定面板详情。Args: board_id (int) 面板ID; current_user (dict) 用户; service (BoardService) 面板服务。Returns: Any 成功响应"""
    return success(data=service.get_board(board_id))


@router.patch("/{board_id}", summary="更新看板", description="更新看板名称或描述", tags=["团队管理"])
def update_board(
    board_id: int,
    body: BoardUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: BoardService = Depends(),
) -> Any:
    """更新面板名称或描述。
    Args: board_id (int) 面板ID; body (BoardUpdate) 面板更新体; current_user (dict) 用户; service (BoardService) 面板服务。
    Returns: Any 成功响应"""
    result = service.update_board(board_id, name=body.name, description=body.description)
    return success(data=result)


@router.delete("/{board_id}", summary="删除看板", description="删除指定看板", tags=["团队管理"])
def delete_board(
    board_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: BoardService = Depends(),
) -> Any:
    """删除指定面板。Args: board_id (int) 面板ID; current_user (dict) 用户; service (BoardService) 面板服务。Returns: Any 成功响应"""
    service.delete_board(board_id)
    return success()


@router.get("/{board_id}/kanban", summary="看板视图", description="获取看板的Kanban视图数据", tags=["团队管理"])
def kanban_view(
    board_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: BoardService = Depends(),
) -> Any:
    """获取面板看板视图数据。Args: board_id (int) 面板ID; current_user (dict) 用户; service (BoardService) 面板服务。Returns: Any 成功响应"""
    return success(data=service.kanban_view(board_id))
