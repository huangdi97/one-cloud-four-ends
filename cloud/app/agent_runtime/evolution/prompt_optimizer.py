"""A/B 测试 prompt 变体，根据反馈自动生成改进后的 prompt。"""

import json
import logging
import random
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from cloud.app.agent_runtime.evolution.feedback_collector import FeedbackCollector

logger = logging.getLogger(__name__)

DEFAULT_OPTIMIZER_PATH = "data/prompt_optimizer.json"


class PromptOptimizer:
    """对 prompt 进行 A/B 测试，基于反馈自动生成并推送优化后的 prompt。

    工作流程：
    1. 注册 prompt 变体到某个实验
    2. 记录每次推理使用的变体及其反馈评分
    3. 统计胜出变体
    4. LLM 根据失败数据自动生成改进 prompt
    """

    def __init__(self, feedback_collector: FeedbackCollector, storage_path: str = DEFAULT_OPTIMIZER_PATH, llm_url: str = ""):
        """Initialize prompt optimizer with feedback collector and A/B test storage."""
        self._feedback = feedback_collector
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._llm_url = llm_url
        self._experiments: dict[str, dict[str, Any]] = {}
        self._trials: dict[str, list[dict]] = defaultdict(list)
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    data = json.load(f)
                self._experiments = data.get("experiments", {})
                self._trials = defaultdict(list, data.get("trials", {}))
            except Exception as e:
                logger.warning("PromptOptimizer: failed to load %s: %s", self._path, e)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(
                {
                    "experiments": self._experiments,
                    "trials": dict(self._trials),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        tmp.replace(self._path)

    def _cheap_llm(self, messages: list[dict]) -> str:
        import urllib.request

        body = json.dumps({"messages": messages, "temperature": 0.3, "max_tokens": 2048}).encode("utf-8")
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

    def create_experiment(self, experiment_id: str, base_prompt: str, variants: list[str], agent_key: str = ""):
        """创建一个 A/B 测试实验。

        Args:
            experiment_id: 实验唯一标识
            base_prompt: 原始 prompt（对照组）
            variants: 变体 prompt 列表（实验组）
            agent_key: 关联的 Agent 标识
        """
        with self._lock:
            self._experiments[experiment_id] = {
                "agent_key": agent_key,
                "base_prompt": base_prompt,
                "variants": variants,
                "active": True,
                "created_at": datetime.utcnow().isoformat(),
                "winner": "",
            }
            self._save()

    def select_variant(self, experiment_id: str) -> tuple[str, str]:
        """为一次调用选择 prompt 变体（含对照组）。

        Args:
            experiment_id: 实验标识

        Returns:
            (variant_id, prompt_text)
        """
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp or not exp.get("active"):
                raise ValueError(f"Experiment '{experiment_id}' not found or inactive")

            base = exp["base_prompt"]
            variants = exp["variants"]
            chosen = random.choice(["base"] + [f"variant_{i}" for i in range(len(variants))])
            prompt = base if chosen == "base" else variants[int(chosen.split("_")[1])]
            return chosen, prompt

    def record_trial(self, experiment_id: str, variant_id: str, rating: float, metadata: dict | None = None):
        """记录一次 A/B 测试结果。

        Args:
            experiment_id: 实验标识
            variant_id: 变体标识 (base / variant_N)
            rating: 评分 1-5 或隐式反馈换算值
            metadata: 附加信息
        """
        with self._lock:
            self._trials[experiment_id].append(
                {
                    "variant_id": variant_id,
                    "rating": rating,
                    "timestamp": datetime.utcnow().isoformat(),
                    "metadata": metadata or {},
                }
            )
            self._save()

    def get_winner(self, experiment_id: str, min_trials: int = 10) -> str:
        """统计实验数据，返回胜出变体。

        Args:
            experiment_id: 实验标识
            min_trials: 最小有效样本数

        Returns:
            胜出的 variant_id（若无胜出返回 "base"）
        """
        with self._lock:
            trials = self._trials.get(experiment_id, [])
            if len(trials) < min_trials:
                return "base"

            scores: dict[str, list[float]] = defaultdict(list)
            for t in trials:
                scores[t["variant_id"]].append(t["rating"])

            best_variant = "base"
            best_avg = sum(scores["base"]) / len(scores["base"]) if scores.get("base") else 0.0
            for vid, ratings in scores.items():
                if vid == "base":
                    continue
                avg = sum(ratings) / len(ratings)
                if avg > best_avg and len(ratings) >= min_trials // 2:
                    best_avg = avg
                    best_variant = vid

            exp = self._experiments.get(experiment_id)
            if exp:
                exp["winner"] = best_variant
                self._save()
            return best_variant

    def auto_improve(self, experiment_id: str, agent_key: str = "") -> str | None:
        """LLM 根据失败 trial 自动生成改进后的 prompt。

        Args:
            experiment_id: 实验标识
            agent_key: 关联的 Agent 标识

        Returns:
            改进后的 prompt 文本，若失败返回 None
        """
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp:
                return None
            trials = self._trials.get(experiment_id, [])
            low_rated = [t for t in trials if t.get("rating", 3) <= 2]

        if not low_rated:
            logger.info("auto_improve: no low-rated trials for %s", experiment_id)
            return None

        examples = json.dumps(low_rated[:5], ensure_ascii=False)
        prompt = (
            f"Original prompt:\n{exp['base_prompt']}\n\n"
            f"Low-rated trials (rating <= 2):\n{examples}\n\n"
            "Analyze why the prompt failed and produce an improved version. "
            'Output ONLY JSON: {"improved_prompt": "...", "rationale": "..."}'
        )
        reply = self._cheap_llm([{"role": "user", "content": prompt}])
        try:
            improved = self._extract_json(reply)
            new_prompt = improved.get("improved_prompt", "")
            if new_prompt:
                with self._lock:
                    exp["variants"].append(new_prompt)
                    self._save()

                if agent_key:
                    self._feedback.record_explicit(
                        agent_key=agent_key,
                        skill_name=f"prompt_opt_{experiment_id}",
                        rating=3,
                        comment=f"auto-improved: {improved.get('rationale', '')}",
                    )
                return new_prompt
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("auto_improve: LLM output parse failed: %s", e)
        return None

    def get_experiment_status(self, experiment_id: str) -> dict[str, Any]:
        """查询实验状态（样本数、各变体平均分、胜出变体）。"""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp:
                return {}
            trials = self._trials.get(experiment_id, [])
            scores: dict[str, list[float]] = defaultdict(list)
            for t in trials:
                scores[t["variant_id"]].append(t["rating"])
            variants_summary = {
                vid: {
                    "trials": len(ratings),
                    "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
                }
                for vid, ratings in scores.items()
            }
            return {
                "experiment_id": experiment_id,
                "agent_key": exp.get("agent_key", ""),
                "active": exp.get("active", False),
                "total_trials": len(trials),
                "winner": exp.get("winner", ""),
                "variants": variants_summary,
                "created_at": exp.get("created_at", ""),
            }
