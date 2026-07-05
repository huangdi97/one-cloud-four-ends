"""Reflexion 反思循环 — Agent 执行后口头反思并存入 episodic memory，下次避开同类错误。"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from cloud.app.agent_runtime.memory.vector_memory import VectorMemory
from shared.config import settings as config_settings

logger = logging.getLogger(__name__)

DEFAULT_REFLECTION_PATH = "data/reflections.json"


class ReflexionLoop:
    """Agent 执行后口头反思 → 存 episodic memory → 下次执行时读取反思 → 避开同类错误。"""

    def __init__(self, storage_path: str = DEFAULT_REFLECTION_PATH, llm_url: str = ""):
        """Initialize reflexion loop with episodic memory and vector search."""
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, list[dict]]] = {}
        self._llm_url = llm_url or config_settings.ai_chat_url
        self._vector_memory = VectorMemory()
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning("ReflexionLoop: failed to load %s: %s", self._path, e)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def _cheap_llm(self, messages: list[dict]) -> str:
        import urllib.request

        body = json.dumps({"messages": messages, "temperature": 0.1, "max_tokens": 1024}).encode("utf-8")
        req = urllib.request.Request(
            self._llm_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as rp:
            data = json.loads(rp.read().decode("utf-8"))
        return data.get("data", {}).get("reply", "")

    @staticmethod
    def _extract_json(raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        return json.loads(raw)

    def reflect(self, agent_key: str, task: str, result: dict, feedback: str) -> dict:
        """Agent 执行后生成口头反思文本。

        Args:
            agent_key: Agent 标识
            task: 执行的任务描述
            result: 执行结果（含 success, data, error 等）
            feedback: 外部反馈信号
        Returns:
            反思条目 dict
        """
        prompt = (
            f"You are an agent reflecting on your own execution.\n"
            f"Task: {task}\n"
            f"Result: {json.dumps(result, ensure_ascii=False)}\n"
            f"Feedback: {feedback}\n\n"
            "Analyze why you succeeded or failed. Output ONLY JSON:\n"
            "{"
            '"lesson": "I failed/succeeded because...", '
            '"root_cause": "the root cause", '
            '"avoidance": "next time I should..."}'
        )
        reply = self._cheap_llm([{"role": "user", "content": prompt}])
        analysis = self._extract_json(reply)
        reflection = {
            "task": task,
            "result": result.get("success", False),
            "feedback": feedback,
            "lesson": analysis.get("lesson", ""),
            "root_cause": analysis.get("root_cause", ""),
            "avoidance": analysis.get("avoidance", ""),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.store_reflection(agent_key, reflection)
        return reflection

    def store_reflection(self, agent_key: str, reflection: dict):
        """将反思写入 episodic memory（reflection.{agent_key} namespace）。"""
        with self._lock:
            if agent_key not in self._data:
                self._data[agent_key] = {"reflections": []}
            self._data[agent_key]["reflections"].append(reflection)
            self._save()

        reflection_text = (
            f"Task: {reflection.get('task', '')} | Lesson: {reflection.get('lesson', '')} | Avoidance: {reflection.get('avoidance', '')}"
        )
        key = f"reflection_{len(self._data.get(agent_key, {}).get('reflections', []))}"
        metadata = {
            "root_cause": reflection.get("root_cause", ""),
            "success": reflection.get("result", False),
            "timestamp": reflection.get("timestamp", ""),
        }
        self._vector_memory.store(
            agent_name=agent_key,
            key=key,
            content=reflection_text,
            metadata=metadata,
            share_with=None,
        )

    def recall_relevant(self, agent_key: str, current_task: str, top_k: int = 3) -> list[dict]:
        """用 embedding 相似度检索与当前任务相关的历史反思。

        Args:
            agent_key: Agent 标识
            current_task: 当前任务描述
            top_k: 返回条数
        Returns:
            相关反思列表
        """
        results = self._vector_memory.search(agent_key, current_task, top_k=top_k, cross_agent=False)
        return results

    def apply_lessons(self, agent_key: str, current_plan: dict) -> dict:
        """读取相关反思，调整当前计划以避开以往错误。

        Args:
            agent_key: Agent 标识
            current_plan: 当前计划 dict（需含 goal 字段）
        Returns:
            调整后的计划 dict
        """
        task = current_plan.get("goal", current_plan.get("task", ""))
        reflections = self.recall_relevant(agent_key, task, top_k=3)
        if not reflections:
            return current_plan

        lessons_text = "\n".join(f"- {r['content']}" for r in reflections)
        prompt = (
            f"Current plan: {json.dumps(current_plan, ensure_ascii=False)}\n\n"
            f"Lessons from past similar tasks:\n{lessons_text}\n\n"
            "Adjust the plan to avoid past mistakes. Reply ONLY the adjusted plan JSON."
        )
        reply = self._cheap_llm([{"role": "user", "content": prompt}])
        try:
            adjusted = self._extract_json(reply)
            return adjusted
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("apply_lessons: failed to parse adjusted plan, using original: %s", e)
            return current_plan

    def get_reflections(self, agent_key: str) -> list[dict]:
        """获取指定 Agent 全部反思记录。"""
        with self._lock:
            return list(self._data.get(agent_key, {}).get("reflections", []))
