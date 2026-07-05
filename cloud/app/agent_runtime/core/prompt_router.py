"""Prompt 版本管理路由 — 版本创建、历史查询、回滚、差异对比。"""

import difflib
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.agent_runtime.core.agent_specs import AGENT_SPECS
from cloud.app.database import DB_PATH
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/agent/prompts", tags=["Agent Prompts"])


class UpdatePromptRequest(BaseModel):
    content: str
    created_by: str = "system"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.post("/{agent_name}", tags=["Agent Prompts"])
def update_prompt(agent_name: str, body: UpdatePromptRequest, user=Depends(require_scope("visit"))):
    """Create a new prompt version for the given agent."""
    if agent_name not in AGENT_SPECS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown agent: {agent_name}")
    db = _get_db()
    try:
        row = db.execute("SELECT MAX(version_id) as max_ver FROM prompt_versions WHERE agent_name=?", (agent_name,)).fetchone()
        next_ver = (row["max_ver"] or 0) + 1
        db.execute(
            "INSERT INTO prompt_versions (agent_name, version_id, content, created_by) VALUES (?, ?, ?, ?)",
            (agent_name, next_ver, body.content, body.created_by),
        )
        db.commit()
        return success(data={"agent_name": agent_name, "version_id": next_ver, "content": body.content})
    finally:
        db.close()


@router.get("/{agent_name}/versions", tags=["Agent Prompts"])
def list_versions(agent_name: str, user=Depends(require_scope("visit"))):
    """List all prompt versions for the agent, newest first."""
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT id, version_id, content, created_at, created_by FROM prompt_versions WHERE agent_name=? ORDER BY version_id DESC",
            (agent_name,),
        ).fetchall()
        return success(data={"agent_name": agent_name, "versions": [dict(r) for r in rows]})
    finally:
        db.close()


@router.post("/{agent_name}/rollback/{version_id}", tags=["Agent Prompts"])
def rollback_prompt(agent_name: str, version_id: int, user=Depends(require_scope("visit"))):
    """Restore a previous prompt version by creating a new version with its content."""
    db = _get_db()
    try:
        row = db.execute("SELECT content FROM prompt_versions WHERE agent_name=? AND version_id=?", (agent_name, version_id)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version {version_id} not found")
        max_row = db.execute("SELECT MAX(version_id) as max_ver FROM prompt_versions WHERE agent_name=?", (agent_name,)).fetchone()
        next_ver = (max_row["max_ver"] or 0) + 1
        db.execute(
            "INSERT INTO prompt_versions (agent_name, version_id, content, created_by) VALUES (?, ?, ?, ?)",
            (agent_name, next_ver, row["content"], "rollback"),
        )
        db.commit()
        return success(data={"agent_name": agent_name, "version_id": next_ver, "rolled_back_to": version_id})
    finally:
        db.close()


@router.get("/{agent_name}/diff", tags=["Agent Prompts"])
def diff_prompt(
    agent_name: str,
    v1: int = Query(description="First version ID"),
    v2: int = Query(description="Second version ID"),
    user=Depends(require_scope("visit")),
):
    """Return a unified diff between two prompt versions."""
    db = _get_db()
    try:
        row1 = db.execute("SELECT content FROM prompt_versions WHERE agent_name=? AND version_id=?", (agent_name, v1)).fetchone()
        row2 = db.execute("SELECT content FROM prompt_versions WHERE agent_name=? AND version_id=?", (agent_name, v2)).fetchone()
        if not row1:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version {v1} not found")
        if not row2:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version {v2} not found")
        diff_lines = list(difflib.unified_diff(row1["content"].splitlines(), row2["content"].splitlines(), lineterm=""))
        return success(data={"agent_name": agent_name, "v1": v1, "v2": v2, "diff": diff_lines})
    finally:
        db.close()
