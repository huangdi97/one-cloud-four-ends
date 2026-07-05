"""用户认证与注册路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from starlette import status

from cloud.app.database import get_db
from cloud.app.services.platform_svc.auth_service import AuthService
from shared.auth import add_token_to_blacklist, verify_token
from shared.base import success

router = APIRouter(prefix="/auth", tags=["认证"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    scope: Optional[str] = "visit"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    old_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


@router.post(
    "/register",
    tags=["auth"],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Creates a new user with username and password. Returns user_id on success.",
)
def register(body: RegisterRequest, db=Depends(get_db)) -> Any:
    """注册新用户。"""
    service = AuthService(db=db)
    result = service.register(body.username, body.password)
    return success(data=result)


@router.post(
    "/login",
    tags=["auth"],
    summary="Authenticate user and get tokens",
    description="Validates credentials and returns access_token and refresh_token.",
)
def login(body: LoginRequest, db=Depends(get_db)) -> Any:
    """用户登录并返回令牌。"""
    service = AuthService(db=db)
    result = service.login(body.username, body.password, body.scope)
    return success(data=result)


@router.post(
    "/refresh",
    tags=["auth"],
    summary="Refresh access token",
    description="Exchange a valid refresh_token for a new access_token.",
)
def refresh(body: RefreshRequest, db=Depends(get_db)) -> Any:
    """刷新访问令牌。"""
    service = AuthService(db=db)
    result = service.refresh(body.refresh_token)
    return success(data=result)


@router.post(
    "/change-password",
    tags=["auth"],
    summary="Change user password",
    description="Authenticates user with old password and updates to new password.",
)
def change_password(body: ChangePasswordRequest, db=Depends(get_db)) -> Any:
    """修改用户密码。"""
    service = AuthService(db=db)
    service.change_password(body.username, body.old_password, body.new_password)
    return success(message="Password changed successfully")


@router.post(
    "/logout",
    tags=["auth"],
    summary="Logout and revoke current token",
    description="Adds the current token to the blacklist so it can no longer be used.",
)
def logout(request: Request, db=Depends(get_db)) -> Any:
    """登出并将当前 token 加入黑名单。"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        verify_token(token, db)
        add_token_to_blacklist(token, db)
    return success(message="Logged out successfully")
