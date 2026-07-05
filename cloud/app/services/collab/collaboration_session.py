"""协作会话管理方法。"""

import uuid
from typing import Optional

from fastapi import HTTPException

from cloud.app.repositories import CollaborationSessionsRepository, CollaborationStepsRepository
from cloud.app.services.collab.collaboration_message import CollaborationMessageMixin


class CollaborationSessionMixin(CollaborationMessageMixin):
    """协作会话创建、步骤推进和查询方法。"""

    def create_session(
        self,
        task_description: str,
        source_entity_id: str,
        source_agent_role: str,
        orchestrator_agent: str,
        routing_strategy: str,
    ) -> dict:
        """创建一个新的协作会话。

        Args:
            task_description: 任务描述
            source_entity_id: 发起协作的实体 ID
            source_agent_role: 发起 Agent 的角色
            orchestrator_agent: 编排 Agent 名称
            routing_strategy: 路由策略标识

        Returns:
            新创建的会话记录字典
        """
        repo = CollaborationSessionsRepository(self._connection())
        sid = f"collab:{uuid.uuid4()}"
        repo.create(
            {
                "session_id": sid,
                "task_description": task_description,
                "source_entity_id": source_entity_id,
                "source_agent_role": source_agent_role,
                "orchestrator_agent": orchestrator_agent,
                "routing_strategy": routing_strategy,
            }
        )
        rows = repo.list_all(conditions=["session_id=?"], params=[sid])
        return rows[0] if rows else None

    def list_sessions(
        self,
        status: Optional[str] = None,
        source_agent_role: Optional[str] = None,
        routing_strategy: Optional[str] = None,
    ) -> list:
        """按条件查询协作会话列表。

        Args:
            status: 可选，按会话状态过滤
            source_agent_role: 可选，按发起 Agent 角色过滤
            routing_strategy: 可选，按路由策略过滤

        Returns:
            会话记录列表，按开始时间降序排列
        """
        repo = CollaborationSessionsRepository(self._connection())
        conditions, params = [], []
        if status:
            conditions.append("status=?")
            params.append(status)
        if source_agent_role:
            conditions.append("source_agent_role=?")
            params.append(source_agent_role)
        if routing_strategy:
            conditions.append("routing_strategy=?")
            params.append(routing_strategy)
        return repo.list_all(
            conditions=conditions or None,
            params=params or None,
            order_by="started_at DESC",
        )

    def get_session(self, session_id: str) -> dict:
        """获取指定会话及其所有步骤的详细信息。

        Args:
            session_id: 协作会话 ID

        Returns:
            包含 session 和 steps 键的字典

        Raises:
            HTTPException: 会话不存在时返回 404
        """
        sess_repo = CollaborationSessionsRepository(self._connection())
        steps_repo = CollaborationStepsRepository(self._connection())
        sess_rows = sess_repo.list_all(conditions=["session_id=?"], params=[session_id])
        if not sess_rows:
            raise HTTPException(status_code=404, detail="Session not found")
        steps = steps_repo.list_all(conditions=["session_id=?"], params=[session_id], order_by="step_order ASC")
        return {"session": sess_rows[0], "steps": steps}
