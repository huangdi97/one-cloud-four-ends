"""MCP守卫服务，负责工具调用的白名单校验、权限检查与频率限制。"""

import json
import os
import time
from datetime import datetime

from fastapi import HTTPException
from starlette import status

from shared.base_service import BaseService

_RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "rules",
)
_WHITELIST_PATH = os.path.join(_RULES_DIR, "mcp_whitelist.json")


def _load_whitelist() -> dict:
    with open(_WHITELIST_PATH, encoding="utf-8") as f:
        return json.load(f)


def _build_allowed_tools(registry: dict) -> frozenset:
    return frozenset(registry.keys())


_WHITELIST = _load_whitelist()
ALLOWED_TOOLS = _build_allowed_tools(_WHITELIST)
TOOL_REGISTRY = _WHITELIST

_rate_buckets: dict[str, list[float]] = {}


class McpGuardService(BaseService):
    """MCP 调用前置校验服务。

    职责：
    - 校验工具是否在白名单内
    - 校验用户角色是否具备权限
    - 校验工具版本是否匹配
    - 频率限制（单工具每分钟最大调用次数）
    - 记录审计日志到 mcp_audit_log 表
    """

    @staticmethod
    def check_tool_access(tool_name: str, user_role: str) -> dict:
        """前置校验：验证工具名、角色权限、频率限制。

        Args:
            tool_name: 工具名称。
            user_role: 用户角色字符串。

        Returns:
            工具注册信息 dict。

        Raises:
            HTTPException 403: 白名单/角色/频率任一不通过。
        """
        if tool_name not in ALLOWED_TOOLS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tool '{tool_name}' is not in the allowed whitelist",
            )

        info = TOOL_REGISTRY[tool_name]
        if user_role not in info["allowed_roles"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not allowed to access tool '{tool_name}'",
            )

        McpGuardService._check_rate_limit(tool_name, info["max_calls_per_min"])

        return info

    @staticmethod
    def validate_tool_version(tool_name: str, version: str) -> bool:
        """版本锁定校验：检查工具版本是否匹配注册表中的版本。

        Args:
            tool_name: 工具名称。
            version: 待校验的版本字符串。

        Returns:
            True 如果版本匹配，否则 False。
        """
        if tool_name not in TOOL_REGISTRY:
            return False
        return TOOL_REGISTRY[tool_name]["version"] == version

    def log_mcp_call(
        self,
        tool_name: str,
        user_id: int,
        user_role: str,
        params: dict,
        result: dict,
        granted: bool = True,
        reason: str = "",
    ) -> int:
        """审计日志：写入 MCP 调用记录到 mcp_audit_log 表。

        Args:
            tool_name: 工具名称。
            user_id: 用户 ID。
            user_role: 用户角色。
            params: 调用参数。
            result: 调用结果。
            granted: 是否授权通过。
            reason: 拒绝原因（granted=False 时填写）。

        Returns:
            新插入记录的 ID。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.db.execute(
            """INSERT INTO mcp_audit_log
               (tool_name, user_id, user_role, params, result, granted, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tool_name,
                user_id,
                user_role,
                json.dumps(params, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                1 if granted else 0,
                reason,
                now,
            ),
        )
        self.db.commit()
        return cursor.lastrowid

    @staticmethod
    def _check_rate_limit(tool_name: str, max_per_min: int) -> None:
        """检查指定工具的频率是否超限。

        Args:
            tool_name: 工具名称。
            max_per_min: 每分钟最大调用次数。

        Raises:
            HTTPException 429: 超过频率限制。
        """
        now = time.time()
        window = 60.0

        bucket = _rate_buckets.setdefault(tool_name, [])
        cutoff = now - window
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= max_per_min:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for tool '{tool_name}': max {max_per_min} calls per minute",
            )

        bucket.append(now)
