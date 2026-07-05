"""成本管控模块，按 token 用量估算并限制 LLM 调用成本。"""

import logging
import sqlite3
from collections import defaultdict
from datetime import date

logger = logging.getLogger(__name__)

_alerted_today: set[tuple[str, str]] = set()


class BudgetExhaustedError(Exception):
    """预算耗尽时抛出的异常。"""


class CostGovernor:
    """LLM 调用成本控制器，累计 token 消耗并在超预算时阻止调用。

    支持用户上下文感知的预算控制：
    - 预算剩余 < 20% 时输出日志告警
    - 预算耗尽时拒绝新请求（抛出 BudgetExhaustedError）
    """

    MAX_COST_PER_TASK = 0.50
    PRICING = {
        "local": {"input_per_million": 0.0, "output_per_million": 0.0},
        "cloud_normal": {"input_per_million": 0.15, "output_per_million": 0.60},
        "cloud_agent": {"input_per_million": 0.45, "output_per_million": 1.80},
    }

    VALID_TASK_TYPES = ("compliance_check", "anomaly_detection", "opportunity_scan", "coaching", "knowledge_query")

    def __init__(self, max_cost: float = 0.50, model: str = "deepseek-chat"):
        """Initialize cost governor with budget and model config."""
        self._max_cost = max_cost
        self._model = model
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_count = 0
        self._step_costs: list[dict] = []
        self._budget_alerts: dict[str, dict] = {}
        self._agent_costs: dict[str, float] = {}
        self._user_context: dict | None = None
        self._alerted_low_budget = False
        self._daily_usage: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._daily_reset_date: str = ""
        self._task_type: str = ""

    def set_task_type(self, task_type: str) -> None:
        """Set the current task type for cost attribution."""
        if task_type and task_type not in self.VALID_TASK_TYPES:
            logger.warning("CostGovernor: unknown task_type '%s', valid: %s", task_type, self.VALID_TASK_TYPES)
        self._task_type = task_type if task_type in self.VALID_TASK_TYPES else ""

    def set_user_context(self, user_context: dict | None) -> None:
        """设置当前请求的用户上下文，影响预算决策。"""
        self._user_context = user_context
        permission_level = (user_context or {}).get("permission_level", "").lower()
        if permission_level in ("admin", "manager", "superuser"):
            self._max_cost = max(self._max_cost, 2.0)
        elif permission_level in ("user", "viewer", ""):
            self._max_cost = min(self._max_cost, 0.50)
        logger.info("CostGovernor: user_context applied, max_cost=%.4f, role=%s", self._max_cost, (user_context or {}).get("role", "unknown"))

    @staticmethod
    def estimate_cost(tokens_input: int, tokens_output: int, model_tier: str) -> float:
        """估算 LLM 调用成本。"""
        pricing = CostGovernor.PRICING.get(model_tier, CostGovernor.PRICING["cloud_normal"])
        return (tokens_input * pricing["input_per_million"] + tokens_output * pricing["output_per_million"]) / 1e6

    def check(self, model: str, input_tokens: int, output_tokens: int, model_tier: str = "cloud_normal") -> bool:
        """检查当前调用是否在预算范围内。若预算耗尽则触发告警并拒绝。"""
        budget_remaining = self._max_cost - self._total_cost
        if budget_remaining <= 0:
            self._fire_exhausted_alert()
            return False
        budget_pct = (budget_remaining / self._max_cost) * 100 if self._max_cost > 0 else 0
        if budget_pct < 20 and not self._alerted_low_budget:
            self._alerted_low_budget = True
            self._fire_low_budget_alert(budget_pct, budget_remaining)
        estimated_cost = self.estimate_cost(input_tokens, output_tokens, model_tier)
        return (self._total_cost + estimated_cost) <= self._max_cost

    def _fire_low_budget_alert(self, budget_pct: float, budget_remaining: float) -> None:
        """预算低于20%时触发告警。"""
        user_id = str((self._user_context or {}).get("user_id", "unknown"))
        today_key = str(date.today())
        dedup_key = (user_id, today_key)
        if dedup_key in _alerted_today:
            return
        _alerted_today.add(dedup_key)
        msg = f"CostGovernor: 预算不足 (remaining={budget_pct:.1f}%, ${budget_remaining:.4f}, user={user_id}) — 请及时充值"
        logger.warning(msg)
        self._send_alert(msg, "high")

    def _fire_exhausted_alert(self) -> None:
        """预算耗尽时触发告警。"""
        user_id = str((self._user_context or {}).get("user_id", "unknown"))
        today_key = str(date.today())
        dedup_key = (user_id, today_key)
        if dedup_key in _alerted_today:
            return
        _alerted_today.add(dedup_key)
        msg = f"CostGovernor: 预算已耗尽 (total_cost=${self._total_cost:.4f}, max_cost=${self._max_cost:.4f}, user={user_id}) — 新请求被拒绝"
        logger.error(msg)
        self._send_alert(msg, "critical")

    def _send_alert(self, message: str, priority: str) -> None:
        try:
            from cloud.app.services.rep_workbench.notification_service import NotificationService

            user_id_str = str((self._user_context or {}).get("user_id", "0"))
            user_id = int(user_id_str) if user_id_str.isdigit() else 0
            svc = NotificationService()
            svc.send(
                user_id=user_id,
                title=f"[CostGovernor][{priority}]",
                body=message,
                category="system_alert",
            )
        except Exception:
            logger.warning("CostGovernor: notification_service unavailable, fallback: %s", message)

    def record(self, model: str, input_tokens: int, output_tokens: int, model_tier: str = "cloud_normal", step: int | None = None) -> float:
        """记录一次 LLM 调用的 token 消耗与成本。"""
        cost = self.estimate_cost(input_tokens, output_tokens, model_tier)
        self._total_cost += cost
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._call_count += 1
        self._step_costs.append(
            {
                "step": step,
                "model": model,
                "model_tier": model_tier,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": round(cost, 9),
            }
        )
        return cost

    def record_step_cost(self, cost_data: dict, step: int | None = None) -> float:
        """记录步骤级成本数据。"""
        input_tokens = int(cost_data.get("input_tokens", 0))
        output_tokens = int(cost_data.get("output_tokens", 0))
        model_tier = cost_data.get("model_tier", "cloud_normal")
        model = cost_data.get("model", self._model)
        if "cost" in cost_data:
            cost = float(cost_data.get("cost", 0.0))
            self._total_cost += cost
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            self._call_count += 1
            self._step_costs.append(
                {
                    "step": step,
                    "model": model,
                    "model_tier": model_tier,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": round(cost, 9),
                }
            )
            return cost
        return self.record(model, input_tokens, output_tokens, model_tier, step)

    def is_over_budget(self) -> bool:
        """检查是否已超出预算。超出时触发告警。"""
        over = self._total_cost > self._max_cost
        if over:
            self._fire_exhausted_alert()
        return over

    def reset(self):
        """重置成本跟踪数据。"""
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_count = 0
        self._step_costs = []
        self._alerted_low_budget = False
        self._user_context = None

    def restore_usage(self, usage: dict | None) -> None:
        """从外部数据恢复成本使用状态。"""
        usage = usage or {}
        self._total_cost = float(usage.get("total_cost", 0.0) or 0.0)
        self._total_input_tokens = int(usage.get("total_input_tokens", 0) or 0)
        self._total_output_tokens = int(usage.get("total_output_tokens", 0) or 0)
        self._call_count = int(usage.get("call_count", 0) or 0)
        self._step_costs = list(usage.get("step_costs", []) or [])

    def record_call(
        self,
        agent_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        trace_id: str = "",
        db=None,
        task_type: str = "",
    ):
        """记录一次 LLM 调用到数据库。"""
        if db is None:
            return
        try:
            db.execute(
                "INSERT INTO agent_cost_tracking (agent_name, model, model_tier, task_type, input_tokens, output_tokens, cost, trace_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (agent_name, model, model, task_type or self._task_type, input_tokens, output_tokens, round(cost, 9), trace_id),
            )
            db.commit()
        except sqlite3.Error:
            logger.exception("Failed to record cost tracking entry")

    def track_task_cost(self, agent_key: str, task_type: str, tokens: int, cost: float, db=None):
        """记录按业务任务类型归因的成本。"""
        if db is None:
            return
        try:
            db.execute(
                "INSERT INTO agent_cost_tracking (agent_name, model, model_tier, task_type, input_tokens, output_tokens, cost) "
                "VALUES (?, '', '', ?, 0, ?, ?)",
                (agent_key, task_type, tokens, round(cost, 9)),
            )
            db.commit()
        except sqlite3.Error:
            logger.exception("Failed to record task cost")

    def get_costs_by_task_type(self, db) -> list[dict]:
        """按任务类型汇总成本。"""
        rows = db.execute(
            "SELECT task_type, SUM(cost) as total_cost, SUM(input_tokens + output_tokens) as total_tokens, "
            "COUNT(*) as call_count "
            "FROM agent_cost_tracking WHERE task_type != '' "
            "GROUP BY task_type ORDER BY total_cost DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_costs_by_agent_and_task_type(self, db, agent_name: str = "") -> list[dict]:
        """按 Agent + 任务类型汇总成本。"""
        if agent_name:
            rows = db.execute(
                "SELECT agent_name, task_type, SUM(cost) as total_cost, SUM(input_tokens + output_tokens) as total_tokens, "
                "COUNT(*) as call_count "
                "FROM agent_cost_tracking WHERE agent_name=? AND task_type != '' "
                "GROUP BY agent_name, task_type ORDER BY total_cost DESC",
                (agent_name,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT agent_name, task_type, SUM(cost) as total_cost, SUM(input_tokens + output_tokens) as total_tokens, "
                "COUNT(*) as call_count "
                "FROM agent_cost_tracking WHERE task_type != '' "
                "GROUP BY agent_name, task_type ORDER BY total_cost DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_costs_by_time_range(self, db, start: str, end: str, agent_name: str = "", task_type: str = "") -> list[dict]:
        """按时间范围查询成本，支持按 agent 和 task_type 筛选。"""
        query = (
            "SELECT agent_name, task_type, SUM(cost) as total_cost, SUM(input_tokens) as total_input, "
            "SUM(output_tokens) as total_output, COUNT(*) as call_count "
            "FROM agent_cost_tracking WHERE timestamp >= ? AND timestamp <= ?"
        )
        params: list[str] = [start, end]
        if agent_name:
            query += " AND agent_name=?"
            params.append(agent_name)
        if task_type:
            query += " AND task_type=?"
            params.append(task_type)
        query += " GROUP BY agent_name, task_type ORDER BY total_cost DESC"
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_daily_costs(self, db, start: str, end: str) -> list[dict]:
        """获取每日成本汇总。"""
        rows = db.execute(
            "SELECT DATE(timestamp) as day, SUM(cost) as total_cost, SUM(input_tokens) as total_input, "
            "SUM(output_tokens) as total_output, COUNT(*) as call_count "
            "FROM agent_cost_tracking WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ? "
            "GROUP BY DATE(timestamp) ORDER BY day",
            (start, end),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_costs_by_agent(self, db) -> list[dict]:
        """获取各 Agent 的成本统计。"""
        rows = db.execute(
            "SELECT agent_name, SUM(cost) as total_cost, SUM(input_tokens) as total_input, "
            "SUM(output_tokens) as total_output, COUNT(*) as call_count "
            "FROM agent_cost_tracking GROUP BY agent_name ORDER BY total_cost DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_costs_by_model(self, db) -> list[dict]:
        """获取各模型的成本统计。"""
        rows = db.execute(
            "SELECT model, SUM(cost) as total_cost, SUM(input_tokens) as total_input, "
            "SUM(output_tokens) as total_output, COUNT(*) as call_count "
            "FROM agent_cost_tracking GROUP BY model ORDER BY total_cost DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def set_budget_alert(self, agent_name: str, threshold: float, callback=None):
        """Register a budget alert callback for a specific agent."""
        self._budget_alerts[agent_name] = {"threshold": threshold, "callback": callback}

    def _check_budget_alerts(self, agent_name: str, cost: float):
        if agent_name not in self._budget_alerts:
            return
        alert = self._budget_alerts[agent_name]
        total = self._agent_costs.get(agent_name, 0.0)
        if total > alert["threshold"]:
            cb = alert["callback"] or (
                lambda an, c, t: logger.warning(
                    "CostGovernor: budget alert for %s, cost=%.4f, total=%.4f, threshold=%.4f", an, c, t, alert["threshold"]
                )
            )
            cb(agent_name, cost, total)

    def record_cost(self, agent_name: str, cost: float) -> float:
        """Record a cost entry for an agent and check budget alerts."""
        self._agent_costs[agent_name] = self._agent_costs.get(agent_name, 0.0) + cost
        self._total_cost += cost
        self._check_budget_alerts(agent_name, cost)
        return cost

    def track_usage(self, agent_name: str, input_tokens: int, output_tokens: int, model: str = "", model_tier: str = "cloud_normal") -> float:
        """记录实际 token 消耗，按天聚合。"""
        cost = self.estimate_cost(input_tokens, output_tokens, model_tier)
        today = str(date.today())
        if self._daily_reset_date != today:
            self._daily_usage.clear()
            self._daily_reset_date = today
        self._daily_usage[agent_name]["cost"] += cost
        self._daily_usage[agent_name]["input_tokens"] += input_tokens
        self._daily_usage[agent_name]["output_tokens"] += output_tokens
        self._daily_usage[agent_name]["call_count"] += 1
        self._daily_usage["_total"]["cost"] += cost
        self.record(model or self._model, input_tokens, output_tokens, model_tier)
        return cost

    def get_daily_usage(self, tenant_id: str = "") -> dict:
        """获取当天所有 Agent 的消耗汇总。"""
        return dict(self._daily_usage)

    def check_budget(self, tenant_id: str = "") -> bool:
        """检查是否超预算，超预算则告警。"""
        total = self._daily_usage.get("_total", {}).get("cost", 0.0)
        if total > self._max_cost:
            msg = f"CostGovernor: 超预算 (daily=${total:.4f}, max=${self._max_cost:.4f}, tenant={tenant_id})"
            logger.error(msg)
            self._fire_exhausted_alert()
            return False
        return True

    def get_cost_by_agent(self, agent_name: str, period_hours: int = 24) -> float:
        """获取指定 Agent 在指定周期内的成本。"""
        return self._agent_costs.get(agent_name, 0.0)

    def get_cost_by_tenant(self, tenant_id: str, period_hours: int = 24) -> float:
        """获取指定租户在指定周期内的成本（未实现多租户时返回0）。"""
        return 0.0

    def get_usage(self) -> dict:
        """获取当前成本使用详情。"""
        step_cost = self._step_costs[-1]["cost"] if self._step_costs else 0.0
        return {
            "model": self._model,
            "total_cost": round(self._total_cost, 6),
            "step_cost": step_cost,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "call_count": self._call_count,
            "max_cost": self._max_cost,
            "step_costs": list(self._step_costs),
        }
