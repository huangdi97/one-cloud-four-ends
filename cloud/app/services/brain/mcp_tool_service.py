"""MCP 工具管理服务。"""

import json
import logging
import sqlite3
from datetime import datetime

from fastapi import HTTPException
from starlette import status

from cloud.app.database import DB_PATH
from cloud.app.repositories import McpToolsRepository
from cloud.app.services.brain.mcp_guard_service import McpGuardService

logger = logging.getLogger(__name__)


class McpToolService:
    """MCP 工具管理服务 — 提供 MCP 工具的注册、查询、移除等管理功能。"""

    @staticmethod
    def _connect():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row(r):
        if not r:
            return None
        d = dict(r)
        for k in ("input_schema", "output_schema"):
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to parse MCP tool JSON field '%s'", k, exc_info=True)
        return d

    def register_tool(self, body, uid, role):
        """注册一个新的 MCP 工具。"""
        McpGuardService.check_tool_access(body.tool_name, role)
        if not McpGuardService.validate_tool_version(body.tool_name, "1.0.0"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Tool '{body.tool_name}' version mismatch, expected {McpGuardService.TOOL_REGISTRY.get(body.tool_name, {}).get('version', 'unknown')}",
            )
        conn = None
        try:
            conn = self._connect()
            repo = McpToolsRepository(conn)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            repo.create(
                {
                    "tool_name": body.tool_name,
                    "description": body.description,
                    "endpoint_url": body.endpoint_url,
                    "input_schema": json.dumps(body.input_schema, ensure_ascii=False),
                    "output_schema": json.dumps(body.output_schema, ensure_ascii=False),
                    "created_by": uid,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            return self._row(repo.get_by_tool_name(body.tool_name))
        finally:
            if conn:
                conn.close()

    def list_tools(self, enabled, role):
        """查询 MCP 工具列表，可选按启用状态过滤。"""
        McpGuardService.check_tool_access("pubmed_search", role)
        conn = None
        try:
            conn = self._connect()
            return [self._row(r) for r in McpToolsRepository(conn).list_filtered(enabled=enabled)]
        finally:
            if conn:
                conn.close()

    def toggle_tool(self, tool_id, role):
        """切换 MCP 工具的启用/禁用状态。"""
        McpGuardService.check_tool_access("pubmed_search", role)
        conn = None
        try:
            conn = self._connect()
            repo = McpToolsRepository(conn)
            if not repo.get_by_id(tool_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tool not found")
            repo.toggle_enabled(tool_id)
            return self._row(repo.get_by_id(tool_id))
        finally:
            if conn:
                conn.close()

    def delete_tool(self, tool_id, role):
        """删除指定的 MCP 工具。"""
        McpGuardService.check_tool_access("market_intel", role)
        conn = None
        try:
            conn = self._connect()
            repo = McpToolsRepository(conn)
            if not repo.get_by_id(tool_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tool not found")
            repo.delete(tool_id)
            return {"deleted": tool_id}
        finally:
            if conn:
                conn.close()
