"""Agent 执行逻辑，包含实例启停与心跳管理。"""

from fastapi import HTTPException
from starlette import status


class AgentExecutionMixin:
    """Agent 执行逻辑，提供实例启停与心跳同步。"""

    def start_instance(self, instance_key):
        """启动实例并注册到 A2A。

        Args:
            instance_key: 实例键
        """
        instance = self.get_instance(instance_key)
        if instance.get("status") == "running":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="instance already running")
        template = self.get_template(instance["template_key"])
        agent_key = instance.get("a2a_agent_key") or f"agent:{instance_key}"
        a2a = self._a2a_service()
        a2a.register_agent(
            key=agent_key,
            name=instance.get("display_name") or instance_key,
            type_="agent_framework",
            description=template.get("description", ""),
            capabilities=template.get("capabilities", []),
            endpoint_url="",
        )
        self.db.execute(
            "UPDATE agent_instances SET status='running', a2a_agent_key=?, last_active_at=CURRENT_TIMESTAMP WHERE instance_key=?",
            (agent_key, instance_key),
        )
        self.db.commit()
        a2a.heartbeat(agent_key)
        return self.get_instance(instance_key)

    def stop_instance(self, instance_key):
        """停止实例并更新 A2A 状态。

        Args:
            instance_key: 实例键
        """
        instance = self.get_instance(instance_key)
        self.db.execute(
            "UPDATE agent_instances SET status='stopped' WHERE instance_key=?",
            (instance_key,),
        )
        self.db.commit()
        agent_key = instance.get("a2a_agent_key")
        if agent_key:
            self._a2a_service().update_status(agent_key, "offline")
        return self.get_instance(instance_key)

    def heartbeat_instance(self, instance_key):
        """发送实例心跳并同步 A2A。

        Args:
            instance_key: 实例键
        """
        instance = self.get_instance(instance_key)
        self.db.execute(
            "UPDATE agent_instances SET last_active_at=CURRENT_TIMESTAMP WHERE instance_key=?",
            (instance_key,),
        )
        self.db.commit()
        agent_key = instance.get("a2a_agent_key")
        if agent_key:
            self._a2a_service().heartbeat(agent_key)
        row = self.db.execute("SELECT last_active_at FROM agent_instances WHERE instance_key=?", (instance_key,)).fetchone()
        return {"status": instance.get("status"), "last_active_at": row["last_active_at"]}

    def _a2a_service(self):
        """返回 A2aRegistryService 实例，用于 Agent 自动注册与心跳同步。

        Returns:
            A2aRegistryService 实例。
        """
        from cloud.app.services.agent_ops.a2a_registry_service import A2aRegistryService

        return A2aRegistryService(db=self.db)
