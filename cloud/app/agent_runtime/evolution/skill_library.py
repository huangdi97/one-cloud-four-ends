"""Voyager 式技能库 — Agent 学到的技能存为可执行代码，下次直接调用。"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from cloud.app.agent_runtime.memory.vector_memory import VectorMemory
from shared.config import settings as config_settings

logger = logging.getLogger(__name__)

DEFAULT_SKILL_PATH = "data/skill_library.json"


class SkillLibrary:
    """技能库 — 记录、检索、改进、统计 Agent 可复用技能。技能存为 Python 可执行代码片段。"""

    def __init__(self, storage_path: str = DEFAULT_SKILL_PATH, llm_url: str = ""):
        """Initialize skill library with persistent storage and vector search."""
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._data: dict[str, list[dict]] = {}
        self._llm_url = llm_url or config_settings.ai_chat_url
        self._vector_memory = VectorMemory()
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning("SkillLibrary: failed to load %s: %s", self._path, e)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def _cheap_llm(self, messages: list[dict]) -> str:
        import urllib.request

        body = json.dumps({"messages": messages, "temperature": 0.1, "max_tokens": 2048}).encode("utf-8")
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

    def record_skill(self, agent_key: str, skill_name: str, code: str, context: dict, success_rate: float = 1.0) -> dict:
        """记录 Agent 学到的技能。

        Args:
            agent_key: 所属 Agent
            skill_name: 技能名称
            code: 可执行 Python 代码
            context: 适用上下文描述
            success_rate: 初始成功率 (0-1)
        Returns:
            存储后的技能条目
        """
        skill = {
            "skill_name": skill_name,
            "agent_key": agent_key,
            "code": code,
            "context": context,
            "success_rate": success_rate,
            "use_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        with self._lock:
            if agent_key not in self._data:
                self._data[agent_key] = []
            existing = [s for s in self._data[agent_key] if s["skill_name"] == skill_name]
            if existing:
                existing[0].update(
                    {
                        "code": code,
                        "context": context,
                        "success_rate": success_rate,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                )
            else:
                self._data[agent_key].append(skill)
            self._save()

        description = json.dumps(context, ensure_ascii=False) if isinstance(context, dict) else str(context)
        search_text = f"Skill: {skill_name}. Context: {description}. Code: {code[:200]}"
        self._vector_memory.store(
            agent_name=agent_key,
            key=f"skill_{skill_name}",
            content=search_text,
            metadata={"skill_name": skill_name, "success_rate": success_rate},
            share_with=["*"],
        )
        return skill

    def find_skill(self, agent_key: str, goal_description: str, top_k: int = 3) -> list[dict]:
        """语义搜索最匹配目标描述的技能。

        Args:
            agent_key: Agent 标识
            goal_description: 目标描述
            top_k: 返回条数
        Returns:
            匹配的技能列表
        """
        results = self._vector_memory.search(agent_key, goal_description, top_k=top_k, cross_agent=True)
        matched = []
        for r in results:
            skill_name = r.get("metadata", {}).get("skill_name", "")
            with self._lock:
                agent_skills = self._data.get(agent_key, [])
                for s in self._data.values():
                    agent_skills.extend(s)
                skill = next((s for s in agent_skills if s["skill_name"] == skill_name), None)
                if skill:
                    entry = dict(skill)
                    entry["search_score"] = r.get("score", 0.0)
                    matched.append(entry)
        return matched

    def refine_skill(self, skill_name: str, failure_feedback: str) -> dict | None:
        """LLM 根据失败反馈改进技能代码。

        Args:
            skill_name: 技能名称
            failure_feedback: 失败反馈描述
        Returns:
            改进后的技能条目，若未找到返回 None
        """
        with self._lock:
            skill = None
            for agent_skills in self._data.values():
                for s in agent_skills:
                    if s["skill_name"] == skill_name:
                        skill = s
                        break
                if skill:
                    break
            if not skill:
                logger.warning("refine_skill: skill '%s' not found", skill_name)
                return None

            prompt = (
                f"Skill name: {skill_name}\n"
                f"Current code:\n```python\n{skill['code']}\n```\n"
                f"Failure feedback: {failure_feedback}\n\n"
                "Fix the code based on feedback. Output ONLY JSON:\n"
                '{"code": "fixed python code", "changes": "what changed and why"}'
            )
            reply = self._cheap_llm([{"role": "user", "content": prompt}])
            try:
                improved = self._extract_json(reply)
                skill["code"] = improved.get("code", skill["code"])
                skill["success_rate"] = max(0.1, skill["success_rate"] - 0.1)
                skill["updated_at"] = datetime.utcnow().isoformat()
                self._save()
                return dict(skill)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                logger.warning("refine_skill: failed to parse improvement: %s", e)
                return None

    def get_skill_stats(self) -> dict[str, dict[str, Any]]:
        """返回每个技能的使用次数 + 成功率。

        Returns:
            {skill_name: {"use_count": int, "success_rate": float, "agent_key": str}}
        """
        stats = {}
        with self._lock:
            for agent_key, skills in self._data.items():
                for s in skills:
                    stats[s["skill_name"]] = {
                        "use_count": s.get("use_count", 0),
                        "success_rate": s.get("success_rate", 0.0),
                        "agent_key": agent_key,
                        "updated_at": s.get("updated_at", ""),
                    }
        return stats

    def record_use(self, skill_name: str, success: bool):
        """记录一次技能使用情况（更新计数和成功率）。"""
        with self._lock:
            for agent_skills in self._data.values():
                for s in agent_skills:
                    if s["skill_name"] == skill_name:
                        s["use_count"] = s.get("use_count", 0) + 1
                        total = s["use_count"]
                        prev_success = s["success_rate"] * (total - 1)
                        s["success_rate"] = (prev_success + (1.0 if success else 0.0)) / total
                        self._save()
                        return
