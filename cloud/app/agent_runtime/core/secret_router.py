"""密钥管理路由 — 设置/更新、删除、列出密钥。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cloud.app.agent_runtime.core.secret_manager import SecretManager
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/agent/secrets", tags=["Agent Secrets"])


class SecretValue(BaseModel):
    value: str


def _get_manager() -> SecretManager:
    return SecretManager()


@router.post("/{key_name}")
def set_secret(key_name: str, body: SecretValue, user=Depends(require_scope("admin"))):
    """Set or update a secret value."""
    mgr = _get_manager()
    mgr.set(key_name, body.value)
    return success(data={"key_name": key_name})


@router.delete("/{key_name}")
def delete_secret(key_name: str, user=Depends(require_scope("admin"))):
    """Delete a secret by key name."""
    mgr = _get_manager()
    mgr.delete(key_name)
    return success(data={"key_name": key_name})


@router.get("")
def list_secrets(user=Depends(require_scope("admin"))):
    """List all secret key names."""
    mgr = _get_manager()
    return success(data={"keys": mgr.list_keys()})
