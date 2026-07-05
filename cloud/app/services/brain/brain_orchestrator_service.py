"""脑编排服务，承接感知输入并协调多类型记忆存储与编排推理。"""

import json

from cloud.app.services.brain.brain_task_scheduler import (
    _now,
    orchestrator_flow,
    schedule_sensory,
)
from shared.base_service import BaseService


class BrainOrchestratorService(BaseService):
    def ingest_sensory(self, input_type: str, raw_content: str, source: str) -> dict:
        """写入一条感知记忆并触发调度。

        Args:
            input_type: 感知输入类型。
            raw_content: 原始输入内容。
            source: 输入来源标识。

        Returns:
            调度后的感知记忆摘要。

        Raises:
            sqlite3.Error: 当感知记忆写入失败时由调度函数抛出。
        """
        return schedule_sensory(self.db, input_type, raw_content, source)

    def get_sensory_buffer(self, limit: int = 50) -> list[dict]:
        """读取未过期的感知记忆缓冲区。

        Args:
            limit: 返回记录数量上限。

        Returns:
            按重要性排序的感知记忆列表。

        Raises:
            sqlite3.Error: 当数据库查询失败时抛出。
        """
        rows = self.db.execute(
            "SELECT * FROM sensory_memory WHERE (expires_at = '' OR expires_at > ?) ORDER BY importance DESC LIMIT ?",
            (_now(), limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_procedural(self, trigger_event: str | None = None) -> list[dict]:
        """列出过程记忆，可按触发事件过滤。

        Args:
            trigger_event: 可选的触发事件关键词。

        Returns:
            过程记忆字典列表。

        Raises:
            sqlite3.Error: 当数据库查询失败时抛出。
        """
        if trigger_event:
            rows = self.db.execute(
                "SELECT * FROM procedural_memory WHERE trigger_conditions LIKE ? ORDER BY invocation_count DESC",
                (f"%{trigger_event}%",),
            ).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM procedural_memory ORDER BY invocation_count DESC").fetchall()
        return [dict(r) for r in rows]

    def create_procedural(self, procedure_key: str, name: str, description: str, steps: str, trigger_conditions: str) -> dict:
        """创建一条过程记忆。

        Args:
            procedure_key: 过程记忆唯一键。
            name: 过程名称。
            description: 过程描述。
            steps: JSON字符串形式的步骤定义。
            trigger_conditions: 触发条件描述。

        Returns:
            新建过程记忆的摘要字典。

        Raises:
            sqlite3.Error: 当过程记忆写入失败时抛出。
        """
        n = _now()
        self.db.execute(
            "INSERT INTO procedural_memory (procedure_key, name, description, steps, trigger_conditions, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (procedure_key, name, description, steps, trigger_conditions, n, n),
        )
        self.db.commit()
        return {"procedure_key": procedure_key, "name": name, "created_at": n}

    def invoke_procedural(self, procedure_key: str, context: dict) -> dict:
        """调用过程记忆并更新调用统计。

        Args:
            procedure_key: 过程记忆唯一键。
            context: 本次调用上下文字典。

        Returns:
            过程步骤、调用次数、上下文和状态信息；不存在时返回错误字典。

        Raises:
            json.JSONDecodeError: 当步骤字段不是合法JSON字符串时抛出。
            sqlite3.Error: 当读取或更新过程记忆失败时抛出。
        """
        row = self.db.execute("SELECT * FROM procedural_memory WHERE procedure_key=?", (procedure_key,)).fetchone()
        if not row:
            return {"error": f"procedure '{procedure_key}' not found"}
        row = dict(row)
        n = _now()
        new_count = (row["invocation_count"] or 0) + 1
        self.db.execute(
            "UPDATE procedural_memory SET invocation_count=?, last_invoked_at=?, updated_at=? WHERE procedure_key=?",
            (new_count, n, n, procedure_key),
        )
        self.db.commit()
        steps_data = json.loads(row["steps"]) if isinstance(row["steps"], str) else row["steps"]
        return {
            "procedure_key": procedure_key,
            "name": row["name"],
            "steps": steps_data,
            "step_count": len(steps_data),
            "invocation_count": new_count,
            "last_invoked_at": n,
            "context": context,
            "status": "ready",
        }

    def orchestrate(self, input_text: str, input_type: str, source: str) -> dict:
        """执行感知输入到记忆编排的完整流程。

        Args:
            input_text: 输入文本。
            input_type: 输入类型。
            source: 输入来源标识。

        Returns:
            编排流程结果字典。

        Raises:
            sqlite3.Error: 当编排流程读写数据库失败时由调度函数抛出。
        """
        return orchestrator_flow(self.db, input_text, input_type, source)

    def _read_memory(self, memory_id: int, memory_type: str) -> dict | None:
        table_map = {
            "episodic": "episodic_memory",
            "sensory": "sensory_memory",
            "procedural": "procedural_memory",
        }
        table = table_map.get(memory_type)
        if not table:
            return None
        row = self.db.execute(f"SELECT * FROM {table} WHERE id=?", (memory_id,)).fetchone()
        return dict(row) if row else None

    def _update_memory_field(self, memory_id: int, memory_type: str, field: str, new_value: str) -> bool:
        table_map = {
            "episodic": "episodic_memory",
            "sensory": "sensory_memory",
            "procedural": "procedural_memory",
        }
        table = table_map.get(memory_type)
        if not table:
            return False
        allowed_fields = {
            "episodic": {"title", "description", "context", "outcome", "valence", "intensity"},
            "sensory": {"raw_content", "importance"},
            "procedural": {"name", "description", "steps", "trigger_conditions"},
        }
        allowed = allowed_fields.get(memory_type, set())
        if field not in allowed:
            return False
        quoted = f'"{field}"'
        self.db.execute(
            f"UPDATE {table} SET {quoted}=?, updated_at=? WHERE id=?",
            (new_value, _now(), memory_id),
        )
        return True
