"""用户管理路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette import status

from cloud.app.services.rep_workbench.user_service import UserService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: str


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    role: Optional[str] = None
    is_active: Optional[bool] = None


def _require_admin(current_user: dict) -> None:
    if current_user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")


@router.get("/", tags=["users"])
def list_users(
    current_user: dict = Depends(require_scope("visit")),
    service: UserService = Depends(),
) -> Any:
    """获取用户列表（需管理员权限）。

    Args:
        current_user: 当前登录用户信息。
        service: 用户服务。

    Returns:
        用户列表。
    """
    _require_admin(current_user)
    users = service.list_users()
    return success(data=users)


@router.get("/{user_id:int}", tags=["users"])
def get_user(
    user_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: UserService = Depends(),
) -> Any:
    """获取指定用户的详细信息（需管理员权限）。

    Args:
        user_id: 用户 ID。
        current_user: 当前登录用户信息。
        service: 用户服务。

    Returns:
        用户详细信息。
    """
    _require_admin(current_user)
    row = service.get_user(user_id)
    return success(data=row)


@router.patch("/{user_id:int}", tags=["users"])
def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: UserService = Depends(),
) -> Any:
    """更新指定用户的角色或状态（需管理员权限）。

    Args:
        user_id: 用户 ID。
        body: 用户更新请求体。
        current_user: 当前登录用户信息。
        service: 用户服务。

    Returns:
        成功响应。
    """
    _require_admin(current_user)

    updates = {}
    if body.role is not None:
        updates["role"] = body.role
    if body.is_active is not None:
        updates["is_active"] = int(body.is_active)

    service.update_user(user_id, updates)
    return success()


@router.delete("/{user_id:int}", tags=["users"])
def delete_user(
    user_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: UserService = Depends(),
) -> Any:
    """删除指定用户（需管理员权限，不能删除自身）。

    Args:
        user_id: 用户 ID。
        current_user: 当前登录用户信息。
        service: 用户服务。

    Returns:
        成功响应。
    """
    _require_admin(current_user)

    if str(current_user["sub"]) == str(user_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot disable your own account")

    service.delete_user(user_id)
    return success()
