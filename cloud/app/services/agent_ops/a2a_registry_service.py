"""A2A (Agent-to-Agent) 注册服务，管理 Agent 注册、心跳、任务路由与事件记录。"""

import json
import uuid

from fastapi import HTTPException
from starlette import status

from cloud.app.services.agent_ops.a2a_discovery import A2aDiscoveryMixin
from shared.base_service import BaseService
from shared.datetime_utils import row_to_dict


class A2aRegistryService(A2aDiscoveryMixin, BaseService):
    """A2A 注册服务，提供 Agent 注册/发现、心跳维护、任务路由与事件审计。"""

    def register_agent(self, key, name, type_, description, capabilities, endpoint_url):
        """注册或更新 Agent 到注册中心。

        Args:
            key: Agent 唯一键
            name: 名称
            type_: 类型
            description: 描述
            capabilities: 能力列表
            endpoint_url: 端点 URL
        """
        caps_str = json.dumps(capabilities, ensure_ascii=False)
        existing = self.db.execute("SELECT id FROM agent_registry WHERE agent_key=?", (key,)).fetchone()
        if existing:
            self.db.execute(
                "UPDATE agent_registry SET agent_name=?, agent_type=?, description=?, "
                "capabilities=?, endpoint_url=?, updated_at=CURRENT_TIMESTAMP WHERE agent_key=?",
                (name, type_, description, caps_str, endpoint_url, key),
            )
        else:
            self.db.execute(
                "INSERT INTO agent_registry (agent_key, agent_name, agent_type, description, "
                "capabilities, endpoint_url, status) VALUES (?, ?, ?, ?, ?, ?, 'online')",
                (key, name, type_, description, caps_str, endpoint_url),
            )
        self._event("register", key)
        self.db.commit()
        return self.get_agent(key)

    def get_agent(self, agent_key):
        """获取 Agent 信息。

        Args:
            agent_key: Agent 键
        """
        row = self.db.execute("SELECT * FROM agent_registry WHERE agent_key=?", (agent_key,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")
        return row_to_dict(row, "capabilities", "metadata", "input_data", "output_data", "detail")

    def heartbeat(self, agent_key):
        """更新 Agent 心跳时间并置为在线。

        Args:
            agent_key: Agent 键
        """
        self.db.execute(
            "UPDATE agent_registry SET last_heartbeat=CURRENT_TIMESTAMP, status='online' WHERE agent_key=?",
            (agent_key,),
        )
        if self.db.rowcount == 0:
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")
        self._event("heartbeat", agent_key)
        self.db.commit()
        return self.get_agent(agent_key)

    def update_status(self, agent_key, status_val):
        """更新 Agent 状态（online/offline/paused）。

        Args:
            agent_key: Agent 键
            status_val: 新状态
        """
        if status_val not in ("online", "offline", "paused"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status")
        self.db.execute(
            "UPDATE agent_registry SET status=?, updated_at=CURRENT_TIMESTAMP WHERE agent_key=?",
            (status_val, agent_key),
        )
        if self.db.rowcount == 0:
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")
        etype = "deregister" if status_val == "offline" else "status_change"
        self._event(etype, agent_key)
        self.db.commit()
        return self.get_agent(agent_key)

    def submit_task(self, source_key, target_key, task_type, input_data, priority):
        """提交 A2A 任务。

        Args:
            source_key: 源 Agent 键
            target_key: 目标 Agent 键
            task_type: 任务类型
            input_data: 输入数据
            priority: 优先级
        """
        task_id = self._task_id()
        input_str = json.dumps(input_data, ensure_ascii=False)
        self.db.execute(
            "INSERT INTO agent_tasks (task_id, source_agent_key, target_agent_key, task_type, input_data, priority) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, source_key, target_key, task_type, input_str, priority),
        )
        self._event("routing", source_key, {"task_id": task_id, "target": target_key})
        self.db.commit()
        return self.get_task(task_id)

    def get_task(self, task_id):
        """获取任务详情。

        Args:
            task_id: 任务 ID
        """
        row = self.db.execute("SELECT * FROM agent_tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
        return row_to_dict(row, "capabilities", "metadata", "input_data", "output_data", "detail")

    def list_tasks(self, status=None, agent_key=None, limit=50):
        """按条件查询任务列表。

        Args:
            status: 按状态筛选
            agent_key: 按 Agent 键筛选（源或目标）
            limit: 最大返回数
        """
        sql = "SELECT * FROM agent_tasks WHERE 1=1"
        params = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if agent_key:
            sql += " AND (source_agent_key=? OR target_agent_key=?)"
            params.extend([agent_key, agent_key])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self.db.execute(sql, params).fetchall()
        return [row_to_dict(r, "capabilities", "metadata", "input_data", "output_data", "detail") for r in rows]

    def _event(self, etype, agent_key, detail=None):
        """向 agent_network_events 表插入一条审计事件记录。

        Args:
            etype: 事件类型（如 register, heartbeat, routing）。
            agent_key: 关联的 Agent 键。
            detail: 可选的事件详情字典。
        """
        detail_str = json.dumps(detail or {}, ensure_ascii=False)
        self.db.execute(
            "INSERT INTO agent_network_events (event_type, agent_key, detail) VALUES (?, ?, ?)",
            (etype, agent_key, detail_str),
        )

    def _task_id(self):
        """生成一个唯一的 A2A 任务 ID。

        Returns:
            a2a: 前缀加 UUID 十六进制字符串。
        """
        return f"a2a:{uuid.uuid4().hex}"


A = A2aRegistryService
A2ARegistryService = A2aRegistryService
