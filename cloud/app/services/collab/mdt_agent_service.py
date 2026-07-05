"""MDT智能体服务，负责多学科团队协作的智能体管理。"""

import json
import logging
from datetime import datetime

from fastapi import HTTPException
from starlette import status

from shared.base_service import BaseService

logger = logging.getLogger(__name__)


class MdtAgentService(BaseService):
    """MdtAgent 服务类。"""

    def get_framework_participants(self, session_id):
        """get_framework_participants 操作。

        Args:
            session_id: 描述
        """
        rows = self.db.execute(
            "SELECT ai.instance_key, ai.display_name, ai.template_key, "
            "art.domain, art.capabilities "
            "FROM agent_instances ai "
            "JOIN agent_role_templates art ON ai.template_key = art.template_key "
            "WHERE ai.status = 'running'"
        ).fetchall()
        result = []
        for r in rows:
            caps = r["capabilities"]
            if isinstance(caps, str) and caps:
                try:
                    caps = json.loads(caps)
                except (json.JSONDecodeError, TypeError):
                    caps = []
            result.append(
                {
                    "agent_instance_key": r["instance_key"],
                    "display_name": r["display_name"],
                    "domain": r["domain"],
                    "capabilities": caps,
                }
            )
        return result

    def assign_task(self, session_id, agent_instance_key, task_content, priority=3):
        """assign_task 操作。

        Args:
            session_id: 描述
            agent_instance_key: 描述
            task_content: 描述
            priority: 描述
        """
        session = self.db.execute("SELECT id FROM mdt_sessions WHERE id=?", (session_id,)).fetchone()
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MDT session not found")
        inst = self.db.execute(
            "SELECT * FROM agent_instances WHERE instance_key=? AND status='running'",
            (agent_instance_key,),
        ).fetchone()
        if not inst:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="agent instance not found or not running",
            )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.db.execute(
            "INSERT INTO mdt_agent_tasks "
            "(session_id, agent_instance_key, task_type, task_content, priority, created_at) "
            "VALUES (?, ?, 'execute', ?, ?, ?)",
            (session_id, agent_instance_key, task_content, priority, now),
        )
        task_id = cursor.lastrowid
        a2a_agent_key = inst["a2a_agent_key"] or ""
        if a2a_agent_key:
            a2a = self._a2a_service()
            a2a_task = a2a.submit_task(
                source_key="mdt_engine",
                target_key=a2a_agent_key,
                task_type="mdt_execute",
                input_data={
                    "session_id": session_id,
                    "task_content": task_content,
                    "priority": priority,
                },
                priority=priority,
            )
            self.db.execute(
                "UPDATE mdt_agent_tasks SET a2a_task_id=? WHERE id=?",
                (a2a_task["task_id"], task_id),
            )
            a2a._event(
                "routing",
                "mdt_engine",
                {
                    "task_id": a2a_task["task_id"],
                    "target": a2a_agent_key,
                },
            )
        self.db.commit()
        return self._get_task(task_id)

    def list_session_tasks(self, session_id):
        """list_session_tasks 操作。

        Args:
            session_id: 描述
        """
        rows = self.db.execute(
            "SELECT * FROM mdt_agent_tasks WHERE session_id=? ORDER BY priority ASC, created_at DESC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_task_status(self, task_id):
        """get_task_status 操作。

        Args:
            task_id: 描述
        """
        row = self.db.execute("SELECT * FROM mdt_agent_tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="task not found")
        task = dict(row)
        a2a_id = task.get("a2a_task_id")
        if a2a_id:
            try:
                a2a = self._a2a_service()
                a2a_task = a2a.get_task(a2a_id)
                task["a2a_status"] = a2a_task.get("status")
                task["a2a_output"] = a2a_task.get("output_data")
            except Exception:  # noqa: BLE001  # A2A service call may fail for network/API reasons
                logger.exception("A2A task status check failed for a2a_id=%s", a2a_id)
                task["a2a_status"] = "unknown"
        return task

    def batch_assign(self, session_id, assignments):
        """batch_assign 操作。

        Args:
            session_id: 描述
            assignments: 描述
        """
        results = []
        for a in assignments:
            try:
                t = self.assign_task(
                    session_id=session_id,
                    agent_instance_key=a["agent_instance_key"],
                    task_content=a["task_content"],
                    priority=a.get("priority", 3),
                )
                results.append(t)
            except HTTPException as e:
                results.append(
                    {
                        "agent_instance_key": a.get("agent_instance_key", ""),
                        "error": e.detail,
                    }
                )
        return results

    def _get_task(self, task_id):
        row = self.db.execute("SELECT * FROM mdt_agent_tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else {}

    def _a2a_service(self):
        from cloud.app.services.agent_ops.a2a_registry_service import A2aRegistryService

        return A2aRegistryService(db=self.db)
