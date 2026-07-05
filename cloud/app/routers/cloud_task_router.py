"""Task router — task CRUD and my-tasks endpoints for boards."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.platform_svc.task_service import TaskService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/boards", tags=["boards"])


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    assignee_id: Optional[int] = None
    due_date: Optional[str] = None
    sort_order: int = 0


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[int] = None
    due_date: Optional[str] = None
    sort_order: Optional[int] = None


@router.post("/{board_id}/tasks", status_code=status.HTTP_201_CREATED, tags=["boards"])
def create_task(
    board_id: int,
    body: TaskCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: TaskService = Depends(),
) -> Any:
    """在指定看板上创建新任务。

    Args:
        board_id: 看板 ID。
        body: 任务创建请求体。
        current_user: 当前登录用户信息。
        service: 任务服务。

    Returns:
        创建的任务对象。
    """
    row = service.create_task(
        board_id=board_id,
        title=body.title,
        description=body.description,
        status_filter=body.status,
        priority=body.priority,
        assignee_id=body.assignee_id,
        due_date=body.due_date,
        sort_order=body.sort_order,
        user_id=int(current_user["sub"]),
    )
    return success(data=row)


@router.get("/{board_id}/tasks", tags=["boards"])
def list_tasks(
    board_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(require_scope("visit")),
    service: TaskService = Depends(),
) -> Any:
    """查询指定看板的任务列表。

    Args:
        board_id: 看板 ID。
        status_filter: 可选的按状态筛选。
        current_user: 当前登录用户信息。
        service: 任务服务。

    Returns:
        任务列表。
    """
    rows = service.list_tasks(board_id, status_filter=status_filter)
    return success(data=rows)


@router.patch("/{board_id}/tasks/{task_id}", tags=["boards"])
def update_task(
    board_id: int,
    task_id: int,
    body: TaskUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: TaskService = Depends(),
) -> Any:
    """更新指定任务的字段。

    Args:
        board_id: 看板 ID。
        task_id: 任务 ID。
        body: 任务更新请求体。
        current_user: 当前登录用户信息。
        service: 任务服务。

    Returns:
        更新后的任务对象。
    """
    row = service.update_task(
        board_id=board_id,
        task_id=task_id,
        title=body.title,
        description=body.description,
        status_filter=body.status,
        priority=body.priority,
        assignee_id=body.assignee_id,
        due_date=body.due_date,
        sort_order=body.sort_order,
    )
    return success(data=row)


@router.delete("/{board_id}/tasks/{task_id}", tags=["boards"])
def delete_task(
    board_id: int,
    task_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: TaskService = Depends(),
) -> Any:
    """删除指定任务。

    Args:
        board_id: 看板 ID。
        task_id: 任务 ID。
        current_user: 当前登录用户信息。
        service: 任务服务。

    Returns:
        成功响应。
    """
    service.delete_task(board_id, task_id)
    return success()


@router.get("/tasks/my", tags=["boards"])
def my_tasks(
    current_user: dict = Depends(require_scope("visit")),
    service: TaskService = Depends(),
) -> Any:
    """获取当前用户的任务列表。

    Args:
        current_user: 当前登录用户信息。
        service: 任务服务。

    Returns:
        当前用户的任务列表。
    """
    rows = service.my_tasks(user_id=int(current_user["sub"]))
    return success(data=rows)
