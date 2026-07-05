"""API 令牌管理。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette import status

from cloud.app.services.platform_svc.api_token_service import ApiTokenService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/tokens", tags=["tokens"])


class CreateTokenRequest(BaseModel):
    name: str


class TokenResponse(BaseModel):
    id: int
    name: str
    created_at: str
    is_active: bool


@router.post("/", status_code=status.HTTP_201_CREATED, tags=["tokens"])
def create_token(
    body: CreateTokenRequest,
    _: dict = Depends(require_scope("visit")),
    service: ApiTokenService = Depends(),
) -> Any:
    user_id = int(current_user["sub"])  # noqa: F821
    return success(data=service.create_token(body.name, user_id))


@router.get("/", tags=["tokens"])
def list_tokens(
    _: dict = Depends(require_scope("visit")),
    service: ApiTokenService = Depends(),
) -> Any:
    user_id = int(current_user["sub"])  # noqa: F821
    return success(data=service.list_tokens(user_id))


@router.delete("/{token_id:int}", tags=["tokens"])
def revoke_token(
    token_id: int,
    _: dict = Depends(require_scope("visit")),
    service: ApiTokenService = Depends(),
) -> Any:
    user_id = int(current_user["sub"])  # noqa: F821
    service.revoke_token(token_id, user_id)
    return success()
