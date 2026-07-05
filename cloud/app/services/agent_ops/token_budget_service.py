"""Token budget management service.

Provides budget configuration, usage tracking, quota checking,
and usage reporting for LLM token consumption per user per model.
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from cloud.app.database import DB_PATH
from cloud.app.services.platform_svc.budget_tracker import BudgetTracker

_RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "rules",
)
_RULES_PATH = os.path.join(_RULES_DIR, "token_budget_rules.json")


@dataclass
class TokenBudgetConfig:
    """Token预算配置，定义每个模型的每日与每次请求的额度上限。"""

    model: str
    max_tokens_per_day: int
    max_tokens_per_request: int
    alert_threshold: float
    user_id: int


def _load_rules() -> dict:
    """从数据库加载 Token 预算状态。"""
    if not os.path.exists(_RULES_PATH):
        return {"default_alert_threshold": 0.8, "models": {}, "overrides": {}}
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class TokenEstimatorMixin:
    """Token 使用估算和预算校验方法。"""

    def check_budget(self, user_id: int, model: str, estimated_tokens: int) -> dict:
        """Check whether an estimated token usage would exceed the user's budget limits.

        Verifies both the per-request limit and the cumulative daily limit.

        Args:
            user_id: The user's ID.
            model: The model name.
            estimated_tokens: The estimated number of tokens for the upcoming request.

        Returns:
            A dict with allowed (bool), reason (str), daily_used (int), and daily_limit (int).
        """
        budget = self.get_budget(user_id, model)
        daily_limit = budget["max_tokens_per_day"]
        request_limit = budget["max_tokens_per_request"]
        alert_threshold = budget["alert_threshold"]
        if estimated_tokens > request_limit:
            return {
                "allowed": False,
                "reason": f"请求 tokens {estimated_tokens} 超过单次上限 {request_limit}",
                "daily_used": 0,
                "daily_limit": daily_limit,
            }
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(tokens), 0) AS total FROM token_usage WHERE user_id=? AND model=? AND usage_date=?",
                (user_id, model, today),
            ).fetchone()
            daily_used = row["total"] if row else 0
        finally:
            conn.close()
        if daily_used + estimated_tokens > daily_limit:
            return {
                "allowed": False,
                "reason": f"每日配额不足：已用 {daily_used} / {daily_limit}，需 {estimated_tokens}",
                "daily_used": daily_used,
                "daily_limit": daily_limit,
            }
        usage_ratio = (daily_used + estimated_tokens) / daily_limit if daily_limit > 0 else 0
        nearing_limit = usage_ratio >= alert_threshold
        return {
            "allowed": True,
            "reason": "ok" if not nearing_limit else f"用量已达 {usage_ratio:.0%}，接近告警阈值 {alert_threshold:.0%}",
            "daily_used": daily_used,
            "daily_limit": daily_limit,
        }


class TokenBudgetService(TokenEstimatorMixin, BudgetTracker):
    """Token预算管理服务，提供配额检查、使用跟踪与消耗报告。"""

    PRICING = {
        "deepseek-chat": {"input_per_million": 0.14, "output_per_million": 0.28},
        "deepseek-v4-pro": {"input_per_million": 0.14, "output_per_million": 0.28},
    }

    def __init__(self):
        """将当前 Token 预算状态持久化到数据库。"""
        self._rules = _load_rules()

    @classmethod
    def get_pricing(cls, model: str) -> dict:
        """返回指定模型的Token计价配置。

        Args:
            model: 模型名称。

        Returns:
            包含每百万输入和输出Token价格的字典。

        Raises:
            KeyError: 不会主动抛出；未知模型返回默认价格。
        """
        return cls.PRICING.get(model, {"input_per_million": 0.14, "output_per_million": 0.28})

    def _get_model_config(self, model: str) -> dict:
        """重置指定月份的 Token 预算为初始值。"""
        models = self._rules.get("models", {})
        config = models.get(model, {})
        if not config:
            config = {
                "max_tokens_per_day": 100000,
                "max_tokens_per_request": 16000,
            }
        return config

    def _get_override(self, user_id: int, model: str) -> Optional[dict]:
        """设置本月的 Token 总预算。"""
        overrides = self._rules.get("overrides", {})
        user_overrides = overrides.get(str(user_id), {})
        return user_overrides.get(model)

    def get_budget(self, user_id: int, model: str) -> dict:
        """读取用户在指定模型上的预算配置。

        Args:
            user_id: 用户ID。
            model: 模型名称。

        Returns:
            包含日限额、单请求限额和告警阈值的预算字典。

        Raises:
            OSError: 当规则文件读取异常时由初始化流程抛出。
        """
        model_config = self._get_model_config(model)
        override = self._get_override(user_id, model)
        alert_threshold = self._rules.get("default_alert_threshold", 0.8)
        if override:
            model_config.update(override)
            if "alert_threshold" in override:
                alert_threshold = override["alert_threshold"]
        return {
            "user_id": user_id,
            "model": model,
            "max_tokens_per_day": model_config.get("max_tokens_per_day", 100000),
            "max_tokens_per_request": model_config.get("max_tokens_per_request", 16000),
            "alert_threshold": alert_threshold,
        }

    def list_alert_configs(self) -> list:
        """列出已有用量记录对应的告警配置。

        Args:
            None.

        Returns:
            用户和模型维度的预算配置列表。

        Raises:
            sqlite3.Error: 当token budget数据库查询失败时抛出。
        """
        from cloud.app.services.platform_svc.budget_tracker import _connect

        conn = _connect()
        try:
            rows = conn.execute("SELECT DISTINCT user_id, model FROM token_budget ORDER BY user_id, model").fetchall()
        finally:
            conn.close()
        results = []
        for row in rows:
            results.append(self.get_budget(row["user_id"], row["model"]))
        return results

    def update_budget(
        self,
        user_id: int,
        model: str,
        max_tokens_per_day: Optional[int] = None,
        max_tokens_per_request: Optional[int] = None,
        alert_threshold: Optional[float] = None,
    ) -> dict:
        """更新用户指定模型的预算覆盖配置。

        Args:
            user_id: 用户ID。
            model: 模型名称。
            max_tokens_per_day: 可选的新每日Token上限。
            max_tokens_per_request: 可选的新单请求Token上限。
            alert_threshold: 可选的新告警阈值。

        Returns:
            更新后的预算配置字典。

        Raises:
            OSError: 当规则目录创建或规则文件写入失败时抛出。
        """
        override_key = str(user_id)
        overrides = self._rules.setdefault("overrides", {})
        user_override = overrides.setdefault(override_key, {})
        model_override = user_override.setdefault(model, {})
        if max_tokens_per_day is not None:
            model_override["max_tokens_per_day"] = max_tokens_per_day
        if max_tokens_per_request is not None:
            model_override["max_tokens_per_request"] = max_tokens_per_request
        if alert_threshold is not None:
            model_override["alert_threshold"] = alert_threshold
        os.makedirs(os.path.dirname(_RULES_PATH), exist_ok=True)
        with open(_RULES_PATH, "w", encoding="utf-8") as f:
            json.dump(self._rules, f, ensure_ascii=False, indent=2)
        return self.get_budget(user_id, model)

    def get_alerts(self) -> list:
        """计算当前触发阈值的Token预算告警。

        Args:
            None.

        Returns:
            达到告警阈值的用户模型用量列表。

        Raises:
            sqlite3.Error: 当用量或预算查询失败时由底层追踪器抛出。
        """
        configs = self.list_alert_configs()
        return super().get_alerts(configs)
