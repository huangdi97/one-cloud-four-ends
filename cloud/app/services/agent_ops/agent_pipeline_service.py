"""Agent 流水线服务，管理多步骤流水线的创建、执行与运行记录。"""

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request
from starlette import status

from cloud.app.repositories import (
    AgentPipelinesRepository,
    PipelineRunsRepository,
    PipelineStepRunsRepository,
    PipelineStepsRepository,
)
from cloud.app.services.agent_ops.agent_pipeline_exec import PipelineRunQueryMixin
from cloud.lg_utils.pipeline_graph import get_pipeline_graph
from shared.base import ApiResponse, success
from shared.base_service import BaseService


class PipelineExecutorMixin:
    """流水线运行创建、LangGraph 执行和步骤结果落库方法。"""

    db: Any
    _p404: Any

    def run_pipeline(self, pipeline_id: int, body, request: Request, uid: int) -> dict:
        """执行流水线，通过 LangGraph 编排多步骤 Agent。

        Args:
            pipeline_id: 流水线 ID
            body: 请求体（含 user_input）
            request: HTTP 请求对象（用于传递 Authorization）
            uid: 执行者 ID

        Returns:
            含 run_id、status 和 step_results 的执行结果
        """
        runs_repo = PipelineRunsRepository(self._connection())
        step_runs_repo = PipelineStepRunsRepository(self._connection())

        self._p404(pipeline_id)
        steps = self.db.execute(
            "SELECT ps.*, ar.system_prompt, ar.name AS ar_name, ar.temperature, ar.max_tokens "
            "FROM pipeline_steps ps JOIN agent_roles ar ON ps.agent_role_id=ar.id "
            "WHERE ps.pipeline_id=? ORDER BY ps.step_order",
            (pipeline_id,),
        ).fetchall()
        if not steps:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Pipeline has no steps")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_id = runs_repo.create(
            {
                "pipeline_id": pipeline_id,
                "user_input": body.user_input,
                "status": "running",
                "started_at": now,
                "created_by": uid,
            }
        )

        auth_header = request.headers.get("Authorization", "")
        graph_steps = []
        for step in steps:
            graph_steps.append(
                {
                    "step_order": step["step_order"],
                    "agent_role_id": step["agent_role_id"],
                    "agent_name": step["ar_name"],
                    "system_prompt": step["system_prompt"],
                    "custom_prompt_override": step["custom_prompt_override"],
                    "temperature": step["temperature"] or 0.7,
                    "max_tokens": step["max_tokens"] or 2048,
                    "input_mapping": json.loads(step["input_mapping"]) if step["input_mapping"] else {},
                }
            )

        initial_state = {
            "steps": graph_steps,
            "current_index": 0,
            "accumulated_outputs": [],
            "current_step_input": None,
            "done": False,
            "auth_header": auth_header,
            "previous_output": "",
            "user_input": body.user_input,
        }

        graph = get_pipeline_graph()
        result = graph.invoke(initial_state)

        step_results = result["accumulated_outputs"]
        final_status = "completed"
        for sr in step_results:
            s_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            matching_step = next((s for s in steps if s["step_order"] == sr["step_order"]), None)
            step_runs_repo.create(
                {
                    "run_id": run_id,
                    "step_order": sr["step_order"],
                    "agent_role_id": matching_step["agent_role_id"] if matching_step else 0,
                    "agent_role_name": sr["agent_name"],
                    "input_data": json.dumps(sr.get("messages", []), ensure_ascii=False),
                    "output_data": sr["output"],
                    "ai_response_raw": sr["output"] if sr["status"] == "completed" else "",
                    "tokens_used": sr.get("tokens", 0),
                    "status": sr["status"],
                    "started_at": s_now,
                    "completed_at": s_now,
                }
            )
            if sr["status"] == "failed":
                final_status = "failed"

        c_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        runs_repo.update(
            run_id,
            {
                "status": final_status,
                "result": json.dumps({"steps": step_results}, ensure_ascii=False),
                "completed_at": c_now,
            },
        )
        return success(data={"run_id": run_id, "status": final_status, "steps": step_results})


class AgentPipelineService(PipelineRunQueryMixin, PipelineExecutorMixin, BaseService):
    """AgentPipeline 服务，提供流水线 CRUD、运行与执行记录查询。"""

    @staticmethod
    def _pd(row) -> dict:
        """将流水线数据库行转为标准字典。

        Args:
            row: 数据库行或字典

        Returns:
            流水线基本信息字典
        """
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "is_active": row["is_active"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _sd(row) -> dict:
        """将步骤数据库行转为标准字典。

        Args:
            row: 数据库行或字典

        Returns:
            步骤基本信息字典
        """
        return {
            "id": row["id"],
            "pipeline_id": row["pipeline_id"],
            "step_order": row["step_order"],
            "agent_role_id": row["agent_role_id"],
            "input_mapping": row["input_mapping"],
            "custom_prompt_override": row["custom_prompt_override"],
            "created_at": row["created_at"],
        }

    def _p404(self, pid: int):
        """按流水线 ID 获取记录，不存在则抛出 404。

        Args:
            pid: 流水线 ID

        Returns:
            流水线记录字典

        Raises:
            HTTPException: 流水线不存在时返回 404
        """
        repo = AgentPipelinesRepository(self._connection())
        row = repo.get_by_id(pid)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
        return row

    def create_pipeline(self, body, uid: int) -> ApiResponse:
        """创建流水线及其步骤。

        Args:
            body: 请求体（含 name、description、steps）
            uid: 创建者 ID

        Returns:
            创建的流水线记录
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pipelines_repo = AgentPipelinesRepository(self._connection())
        steps_repo = PipelineStepsRepository(self._connection())
        pid = pipelines_repo.create(
            {
                "name": body.name,
                "description": body.description,
                "created_by": uid,
                "created_at": now,
                "updated_at": now,
            }
        )
        for s in body.steps:
            steps_repo.create(
                {
                    "pipeline_id": pid,
                    "step_order": s.step_order,
                    "agent_role_id": s.agent_role_id,
                    "input_mapping": json.dumps(s.input_mapping, ensure_ascii=False),
                    "custom_prompt_override": s.custom_prompt_override,
                }
            )
        return self._pd(pipelines_repo.get_by_id(pid))

    def list_pipelines(self) -> ApiResponse:
        """列出所有流水线（含步骤数）。

        Returns:
            流水线列表
        """
        pipelines_repo = AgentPipelinesRepository(self._connection())
        rows = pipelines_repo.list_all(order_by="created_at DESC")
        pipeline_ids = [r["id"] for r in rows]
        step_counts = {}
        if pipeline_ids:
            placeholders = ",".join("?" * len(pipeline_ids))
            count_rows = self.db.execute(
                f"SELECT pipeline_id, COUNT(*) AS cnt FROM pipeline_steps WHERE pipeline_id IN ({placeholders}) GROUP BY pipeline_id",
                pipeline_ids,
            ).fetchall()
            step_counts = {r["pipeline_id"]: r["cnt"] for r in count_rows}
        result = [{**self._pd(r), "step_count": step_counts.get(r["id"], 0)} for r in rows]
        return result

    def get_pipeline(self, pipeline_id: int) -> ApiResponse:
        """获取流水线详情（含步骤列表）。

        Args:
            pipeline_id: 流水线 ID

        Returns:
            流水线记录含步骤
        """
        steps_repo = PipelineStepsRepository(self._connection())
        row = self._p404(pipeline_id)
        steps = steps_repo.list_all(conditions=["pipeline_id=?"], params=[pipeline_id], order_by="step_order ASC")
        return {**self._pd(row), "steps": [self._sd(s) for s in steps]}

    def delete_pipeline(self, pipeline_id: int) -> ApiResponse:
        """删除流水线及其关联的步骤和运行记录。

        Args:
            pipeline_id: 流水线 ID

        Returns:
            成功响应
        """
        pipelines_repo = AgentPipelinesRepository(self._connection())
        self._p404(pipeline_id)
        self.db.execute("DELETE FROM pipeline_steps WHERE pipeline_id=?", (pipeline_id,))
        self.db.execute("DELETE FROM pipeline_runs WHERE pipeline_id=?", (pipeline_id,))
        pipelines_repo.delete(pipeline_id)
        return success()
