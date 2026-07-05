"""协作服务，管理 Agent 技能注册、协作会话与语义路由。"""

import json
from typing import Optional

from fastapi import HTTPException

from cloud.app.repositories import (
    AgentSkillsRepository,
    CollaborationSessionsRepository,
    CollaborationStepsRepository,
)
from cloud.app.services.collab.collaboration_session import CollaborationSessionMixin
from shared.base_service import BaseService


class CollaborationService(CollaborationSessionMixin, BaseService):
    """协作服务，提供技能管理、会话编排与语义路由功能。"""

    def register_skill(
        self,
        skill_name: str,
        agent_role: str,
        description: str,
        entity_types: list[str],
        capabilities: list[str],
        confidence: float,
        priority: int,
    ) -> dict:
        """注册一个新的 Agent 技能。

        Args:
            skill_name: 技能名称
            agent_role: 关联的 Agent 角色
            description: 技能描述
            entity_types: 支持处理的实体类型列表
            capabilities: 技能能力标签列表
            confidence: 置信度评分 (0.0-1.0)
            priority: 调度优先级，数值越小越优先

        Returns:
            新创建的技能记录字典
        """
        repo = AgentSkillsRepository(self._connection())
        row_id = repo.create(
            {
                "skill_name": skill_name,
                "agent_role": agent_role,
                "description": description,
                "entity_types": json.dumps(entity_types, ensure_ascii=False),
                "capabilities": json.dumps(capabilities, ensure_ascii=False),
                "confidence": confidence,
                "priority": priority,
            }
        )
        return repo.get_by_id(row_id)

    def list_skills(self, agent_role: Optional[str] = None, enabled: Optional[int] = None) -> list:
        """按条件查询已注册的技能列表。

        Args:
            agent_role: 可选，按 Agent 角色过滤
            enabled: 可选，按启用状态过滤 (1=启用, 0=禁用)

        Returns:
            技能记录列表，按优先级升序排列
        """
        repo = AgentSkillsRepository(self._connection())
        conditions, params = [], []
        if agent_role:
            conditions.append("agent_role=?")
            params.append(agent_role)
        if enabled is not None:
            conditions.append("enabled=?")
            params.append(enabled)
        return repo.list_all(
            conditions=conditions or None,
            params=params or None,
            order_by="priority ASC",
        )

    def delete_skill(self, skill_id: int) -> None:
        """删除指定技能。

        Args:
            skill_id: 待删除的技能 ID

        Raises:
            HTTPException: 技能不存在时返回 404
        """
        repo = AgentSkillsRepository(self._connection())
        row = repo.get_by_id(skill_id)
        if not row:
            raise HTTPException(status_code=404, detail="Skill not found")
        repo.delete(skill_id)

    def semantic_route(
        self,
        task_description: str,
        entity_type: str,
        entity_id: str,
        routing_strategy: str,
    ) -> dict:
        """根据实体类型进行语义匹配路由，返回最佳匹配的技能。

        Args:
            task_description: 任务描述
            entity_type: 实体类型，用于匹配技能的 entity_types 字段
            entity_id: 实体 ID
            routing_strategy: 路由策略标识

        Returns:
            包含匹配结果和最佳匹配技能的字典

        Raises:
            HTTPException: 无匹配技能时返回 404
        """
        repo = AgentSkillsRepository(self._connection())
        if entity_type:
            like = f"%{entity_type}%"
            skills = repo.list_all(
                conditions=["enabled=1", "entity_types LIKE ?"],
                params=[like],
                order_by="priority ASC, confidence DESC",
            )
        else:
            skills = repo.list_all(conditions=["enabled=1"], order_by="priority ASC, confidence DESC")

        if not skills:
            raise HTTPException(status_code=404, detail="No matching agent skills found")

        return {
            "task_description": task_description,
            "entity_type": entity_type,
            "routing_strategy": routing_strategy,
            "matched_skills": skills,
            "best_match": skills[0],
        }

    def dashboard(self) -> dict:
        """获取协作仪表盘汇总数据。

        Returns:
            包含技能统计、会话统计、步骤统计、热门 Agent 角色及最近会话的字典
        """
        skills_repo = AgentSkillsRepository(self._connection())
        sess_repo = CollaborationSessionsRepository(self._connection())
        steps_repo = CollaborationStepsRepository(self._connection())

        total_skills = skills_repo.count()
        active_skills = skills_repo.count(conditions=["enabled=1"])
        total_sessions = sess_repo.count()
        active_sessions = sess_repo.count(conditions=["status='active'"])
        completed_sessions = sess_repo.count(conditions=["status='completed'"])
        total_steps = steps_repo.count()
        completed_steps = steps_repo.count(conditions=["status='completed'"])

        top_skills = steps_repo.list_all(order_by="agent_role ASC")
        role_counts = {}
        for s in top_skills:
            role = s["agent_role"]
            role_counts[role] = role_counts.get(role, 0) + 1
        top_agent_roles = sorted(
            [{"agent_role": k, "step_count": v} for k, v in role_counts.items()],
            key=lambda x: x["step_count"],
            reverse=True,
        )[:5]

        recent = sess_repo.list_all(order_by="started_at DESC")[:5]

        return {
            "skills": {"total": total_skills, "active": active_skills},
            "sessions": {
                "total": total_sessions,
                "active": active_sessions,
                "completed": completed_sessions,
            },
            "steps": {"total": total_steps, "completed": completed_steps},
            "top_agent_roles": top_agent_roles,
            "recent_sessions": recent,
        }
