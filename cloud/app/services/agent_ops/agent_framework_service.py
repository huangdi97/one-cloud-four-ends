"""Agent 框架服务，管理角色模板与实例的生命周期（创建、启停、心跳）。"""

import json
import logging

from fastapi import HTTPException
from starlette import status

from cloud.app.services.agent_ops.agent_execution import AgentExecutionMixin
from shared.base_service import BaseService
from shared.datetime_utils import row_to_dict

logger = logging.getLogger(__name__)


class AgentFrameworkService(AgentExecutionMixin, BaseService):
    """Agent 框架服务，提供模板管理、实例生命周期与 A2A 自动注册。"""

    def list_templates(self, domain=None):
        """列出 Agent 角色模板。

        Args:
            domain: 按领域筛选

        Returns:
            模板列表
        """
        sql = "SELECT * FROM agent_role_templates WHERE 1=1"
        params = []
        if domain:
            sql += " AND domain=?"
            params.append(domain)
        rows = self.db.execute(sql, params).fetchall()
        return [row_to_dict(r, "capabilities", "default_config", "triggers", "endpoints", "config_overrides", "metrics") for r in rows]

    def get_template(self, template_key):
        """获取指定模板。

        Args:
            template_key: 模板键
        """
        row = self.db.execute("SELECT * FROM agent_role_templates WHERE template_key=?", (template_key,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
        return row_to_dict(row, "capabilities", "default_config", "triggers", "endpoints", "config_overrides", "metrics")

    def create_template(self, key, name, description, domain, capabilities, default_config, triggers, endpoints):
        """创建角色模板。

        Args:
            key: 模板唯一键
            name: 名称
            description: 描述
            domain: 领域
            capabilities: 能力列表
            default_config: 默认配置
            triggers: 触发器配置
            endpoints: 端点配置
        """
        self.db.execute(
            "INSERT INTO agent_role_templates (template_key, name, description, domain, capabilities, default_config, triggers, endpoints) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                key,
                name,
                description,
                domain,
                json.dumps(capabilities, ensure_ascii=False),
                json.dumps(default_config, ensure_ascii=False),
                json.dumps(triggers, ensure_ascii=False),
                json.dumps(endpoints, ensure_ascii=False),
            ),
        )
        self.db.commit()
        return self.get_template(key)

    def list_instances(self, status=None, template_key=None):
        """列出 Agent 实例。

        Args:
            status: 按状态筛选
            template_key: 按模板键筛选

        Returns:
            实例列表
        """
        sql = "SELECT * FROM agent_instances WHERE 1=1"
        params = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if template_key:
            sql += " AND template_key=?"
            params.append(template_key)
        rows = self.db.execute(sql, params).fetchall()
        return [row_to_dict(r, "capabilities", "default_config", "triggers", "endpoints", "config_overrides", "metrics") for r in rows]

    def get_instance(self, instance_key):
        """获取指定实例。

        Args:
            instance_key: 实例键
        """
        row = self.db.execute("SELECT * FROM agent_instances WHERE instance_key=?", (instance_key,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="instance not found")
        return row_to_dict(row, "capabilities", "default_config", "triggers", "endpoints", "config_overrides", "metrics")

    def create_instance(self, instance_key, template_key, display_name, bind_to_end, config_overrides):
        """创建 Agent 实例，可选自动注册到 A2A。

        Args:
            instance_key: 实例唯一键
            template_key: 关联模板键
            display_name: 显示名称
            bind_to_end: 绑定端点
            config_overrides: 配置覆盖
        """
        template = self.get_template(template_key)
        self.db.execute(
            "INSERT INTO agent_instances (instance_key, template_key, display_name, bind_to_end, config_overrides) VALUES (?, ?, ?, ?, ?)",
            (instance_key, template_key, display_name, bind_to_end, json.dumps(config_overrides, ensure_ascii=False)),
        )
        self.db.commit()
        instance = self.get_instance(instance_key)
        default_config = template.get("default_config", {})
        if default_config.get("auto_register", False):
            a2a = self._a2a_service()
            agent_key = f"agent:{instance_key}"
            caps = template.get("capabilities", [])
            a2a.register_agent(
                key=agent_key,
                name=display_name or instance_key,
                type_="agent_framework",
                description=template.get("description", ""),
                capabilities=caps,
                endpoint_url="",
            )
            self.db.execute(
                "UPDATE agent_instances SET a2a_agent_key=? WHERE instance_key=?",
                (agent_key, instance_key),
            )
            self.db.commit()
            instance = self.get_instance(instance_key)
        return instance
