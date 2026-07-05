"""收集隐式反馈（信号推断）和显式反馈（用户评分 / 文本评价），存入持久化存储。

支持从 SharedState `dialogue.feedback.*` namespace 导入反馈，归类并检测≥3次同类反馈模式，
自动写入 SkillLibrary 作为避坑规则。
"""

import json
import logging
import threading
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from cloud.app.agent_runtime.core.shared_state import get_shared_state
from cloud.app.agent_runtime.evolution.skill_library import SkillLibrary

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

DEFAULT_FEEDBACK_PATH = "data/feedback.json"


class FeedbackCollector:
    """收集隐式 + 显式反馈，按 Agent 和技能汇总。

    反馈类型：
    - 显式：用户评分（1-5）、文本评价
    - 隐式：UserStatePerceiver 推断的意图 / 情绪 / 疲劳度
    """

    def __init__(self, storage_path: str = DEFAULT_FEEDBACK_PATH):
        """Initialize feedback collector with persistent JSON storage."""
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._data: dict[str, list[dict]] = defaultdict(list)
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    raw = json.load(f)
                self._data = defaultdict(list, raw)
            except Exception as e:
                logger.warning("FeedbackCollector: failed to load %s: %s", self._path, e)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(dict(self._data), f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def record_explicit(self, agent_key: str, skill_name: str, rating: int, comment: str = ""):
        """记录显式用户反馈（评分 + 可选文字评价）。

        Args:
            agent_key: Agent 标识
            skill_name: 技能 / 动作名称
            rating: 评分 1-5
            comment: 文本评价
        """
        if not 1 <= rating <= 5:
            raise ValueError("rating must be between 1 and 5")
        entry = {
            "type": "explicit",
            "agent_key": agent_key,
            "skill_name": skill_name,
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.utcnow().isoformat(),
        }
        with self._lock:
            self._data[agent_key].append(entry)
            self._save()

    def record_implicit(self, agent_key: str, skill_name: str, inferred: dict):
        """记录隐式反馈（从用户状态推断的信号）。

        Args:
            agent_key: Agent 标识
            skill_name: 技能 / 动作名称
            inferred: UserStatePerceiver 推断的状态 dict（含 intent, emotion, fatigue, engagement）
        """
        entry = {
            "type": "implicit",
            "agent_key": agent_key,
            "skill_name": skill_name,
            "inferred": inferred,
            "timestamp": datetime.utcnow().isoformat(),
        }
        with self._lock:
            self._data[agent_key].append(entry)
            self._save()

    def get_feedback(self, agent_key: str, skill_name: str | None = None, feedback_type: str | None = None) -> list[dict]:
        """查询反馈记录。

        Args:
            agent_key: Agent 标识
            skill_name: 可选，按技能过滤
            feedback_type: 可选，按类型过滤 (explicit / implicit)

        Returns:
            匹配的反馈条目列表
        """
        with self._lock:
            records = list(self._data.get(agent_key, []))
        if skill_name:
            records = [r for r in records if r.get("skill_name") == skill_name]
        if feedback_type:
            records = [r for r in records if r.get("type") == feedback_type]
        return records

    def get_avg_rating(self, agent_key: str, skill_name: str | None = None) -> float:
        """计算显式反馈的平均评分。

        Args:
            agent_key: Agent 标识
            skill_name: 可选，按技能过滤

        Returns:
            平均评分 1-5，无数据时返回 0.0
        """
        explicit = self.get_feedback(agent_key, skill_name=skill_name, feedback_type="explicit")
        ratings = [r["rating"] for r in explicit if "rating" in r]
        if not ratings:
            return 0.0
        return round(sum(ratings) / len(ratings), 2)

    def get_summary(self, agent_key: str) -> dict[str, Any]:
        """返回指定 Agent 的反馈汇总。

        Args:
            agent_key: Agent 标识

        Returns:
            {total, explicit_count, implicit_count, avg_rating, recent_negative}
        """
        records = self.get_feedback(agent_key)
        explicit = [r for r in records if r.get("type") == "explicit"]
        implicit = [r for r in records if r.get("type") == "implicit"]
        return {
            "total": len(records),
            "explicit_count": len(explicit),
            "implicit_count": len(implicit),
            "avg_rating": self.get_avg_rating(agent_key),
            "recent_negative": [r for r in explicit[-20:] if r.get("rating", 5) <= 2],
        }

    def clear(self, agent_key: str | None = None):
        """清空反馈数据。指定 agent_key 时只清空该 Agent。"""
        with self._lock:
            if agent_key:
                self._data.pop(agent_key, None)
            else:
                self._data.clear()
            self._save()

    def collect_from_shared_state(self) -> int:
        """从 SharedState `dialogue.feedback.*` namespace 读取反馈条目并导入本地存储。

        读取所有 feedback 条目，按 agent_key 归类后存入本地 storage_path。
        返回新导入的条目数（排除重复）。
        """
        ss = get_shared_state()
        entries = ss.read("dialogue.feedback", min_confidence=0.0)
        imported = 0
        for entry in entries:
            value = entry.value if isinstance(entry.value, dict) else {}
            agent_key = value.get("agent_key", "unknown")
            feedback_id = value.get("feedback_id", entry.key)
            with self._lock:
                existing_ids = {r.get("feedback_id", "") for r in self._data.get(agent_key, [])}
                if feedback_id not in existing_ids:
                    feedback_entry = {
                        "type": "explicit",
                        "source": "shared_state_dialogue",
                        "feedback_id": feedback_id,
                        "agent_key": agent_key,
                        "skill_name": "dialogue_feedback",
                        "rating": 1,
                        "comment": value.get("user_message", ""),
                        "evidence": entry.evidence,
                        "timestamp": entry.timestamp or datetime.utcnow().isoformat(),
                    }
                    self._data[agent_key].append(feedback_entry)
                    imported += 1
        if imported:
            self._save()
            logger.info("FeedbackCollector: imported %d feedback entries from SharedState", imported)
        return imported

    def detect_patterns(self, min_count: int = 3) -> list[dict]:
        """检测同类反馈模式（同一 Agent 同一关键词出现≥3次），写入 SkillLibrary。

        Returns:
            检测到的模式列表，每条含 agent_key / keyword / count / created_rule 状态
        """

        skill_lib = SkillLibrary()
        patterns_found = []
        keyword_counter: dict[str, Counter] = defaultdict(Counter)

        with self._lock:
            for agent_key, records in self._data.items():
                for r in records:
                    comment = r.get("comment", "")
                    # 提取关键否定词
                    for kw in ["误报", "不对", "错了", "假的", "不是这样"]:
                        if kw in comment:
                            keyword_counter[agent_key][kw] += 1

        for agent_key, counter in keyword_counter.items():
            for keyword, count in counter.items():
                if count >= min_count:
                    # 生成避坑规则代码
                    rule_code = (
                        f"# 避坑规则: {keyword} (触发{count}次)\n"
                        f"def avoid_{keyword}_pattern(data: dict) -> bool:\n"
                        f'    """检测是否存在 {keyword} 模式 — 基于用户反馈自动生成。"""\n'
                        f"    return False  # TODO: 实现具体检测逻辑\n"
                    )
                    rule_context = {
                        "agent_key": agent_key,
                        "keyword": keyword,
                        "trigger_count": count,
                        "source": "feedback_collector_pattern_detection",
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    skill_lib.record_skill(
                        agent_key=agent_key,
                        skill_name=f"avoid_{keyword}_pattern",
                        code=rule_code,
                        context=rule_context,
                        success_rate=0.5,
                    )
                    patterns_found.append(
                        {
                            "agent_key": agent_key,
                            "keyword": keyword,
                            "count": count,
                            "rule_created": f"avoid_{keyword}_pattern",
                        }
                    )
                    logger.info(
                        "FeedbackCollector: detected pattern agent=%s keyword=%s count=%d — rule created",
                        agent_key,
                        keyword,
                        count,
                    )

        return patterns_found
