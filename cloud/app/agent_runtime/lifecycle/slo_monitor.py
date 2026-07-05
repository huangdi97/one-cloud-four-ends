"""SLO 监控 — 服务等级目标定义与检查。"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class SLOConfig:
    """单个 Agent 的服务等级目标配置。"""

    latency_p99_ms: float = 5000
    error_rate: float = 0.05
    uptime: float = 0.995

    def to_dict(self) -> dict:
        """Return SLO config as a plain dictionary."""
        return {
            "latency_p99_ms": self.latency_p99_ms,
            "error_rate": self.error_rate,
            "uptime": self.uptime,
        }


# 默认 SLO 配置
DEFAULT_SLOS: dict[str, SLOConfig] = {
    "compliance_monitor": SLOConfig(latency_p99_ms=8000, error_rate=0.05, uptime=0.995),
    "sales_suggestion": SLOConfig(latency_p99_ms=3000, error_rate=0.03, uptime=0.995),
    "sales_coach_analyst": SLOConfig(latency_p99_ms=15000, error_rate=0.10, uptime=0.99),
    "knowledge_worker": SLOConfig(latency_p99_ms=5000, error_rate=0.05, uptime=0.995),
    "opportunity_scanner": SLOConfig(latency_p99_ms=5000, error_rate=0.05, uptime=0.995),
}

_breach_log: list[dict] = []
_alert_handlers: list[callable] = []


def register_alert_handler(handler: callable) -> None:
    """注册告警处理器函数。handler 签名: (agent_name, slo_name, current, threshold) -> None"""
    _alert_handlers.append(handler)


def check_slo(agent_name: str, metrics: dict) -> dict:
    """检查一个 Agent 的指标是否满足 SLO。返回 {passed, checks: [{name, passed, current, threshold}]}"""
    config = DEFAULT_SLOS.get(agent_name)
    if config is None:
        return {"passed": True, "checks": []}

    checks = []
    if "latency_p99_ms" in metrics:
        current = metrics["latency_p99_ms"]
        passed = current <= config.latency_p99_ms
        checks.append(
            {
                "name": "latency_p99",
                "passed": passed,
                "current_ms": current,
                "threshold_ms": config.latency_p99_ms,
            }
        )
        if not passed:
            report_slo_breach(agent_name, "latency_p99", current, config.latency_p99_ms)

    if "error_rate" in metrics:
        current = metrics["error_rate"]
        passed = current <= config.error_rate
        checks.append(
            {
                "name": "error_rate",
                "passed": passed,
                "current": current,
                "threshold": config.error_rate,
            }
        )
        if not passed:
            report_slo_breach(agent_name, "error_rate", current, config.error_rate)

    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def get_slo_status() -> dict:
    """返回所有已配置 Agent 的 SLO 状态摘要。"""
    return {
        name: {
            "latency_p99_ms": cfg.latency_p99_ms,
            "error_rate": cfg.error_rate,
            "uptime": cfg.uptime,
        }
        for name, cfg in DEFAULT_SLOS.items()
    }


def report_slo_breach(agent_name: str, slo_name: str, current: float, threshold: float) -> None:
    """记录 SLO 违约。"""
    from datetime import datetime

    _breach_log.append(
        {
            "agent_name": agent_name,
            "slo_name": slo_name,
            "current": current,
            "threshold": threshold,
            "timestamp": datetime.now().isoformat(),
        }
    )


def get_breach_log(limit: int = 20) -> list[dict]:
    """获取最近的 SLO 违约记录。"""
    return _breach_log[-limit:]


def get_breach_summary(hours: int = 24) -> dict:
    """返回过去 N 小时的 SLO 违约汇总。"""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    recent = [b for b in _breach_log if b.get("timestamp", "") >= cutoff]
    by_agent: dict[str, int] = {}
    for b in recent:
        by_agent[b["agent_name"]] = by_agent.get(b["agent_name"], 0) + 1
    return {
        "period_hours": hours,
        "total_breaches": len(recent),
        "by_agent": by_agent,
        "breaches": recent[-20:],
    }


_alert_log_path: str = os.environ.get("AGENT_ALERT_LOG", "data/agent_alerts.log")


def _ensure_alert_log_dir() -> None:
    log_dir = os.path.dirname(_alert_log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)


def _rotate_alert_log() -> None:
    """单文件最大5MB，超过自动归档。"""
    max_bytes = 5 * 1024 * 1024
    try:
        if os.path.getsize(_alert_log_path) > max_bytes:
            import shutil

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = f"{_alert_log_path}.{timestamp}"
            shutil.copy2(_alert_log_path, archive_path)
            open(_alert_log_path, "w").close()
            # 保留最近10个归档
            archive_dir = os.path.dirname(_alert_log_path)
            archives = sorted(
                [f for f in os.listdir(archive_dir) if f.startswith(os.path.basename(_alert_log_path) + ".")],
            )
            for old in archives[:-10]:
                os.remove(os.path.join(archive_dir, old))
    except (OSError, FileNotFoundError):
        pass


def _write_alert_file(agent_name: str, slo_name: str, current: float, threshold: float) -> None:
    _ensure_alert_log_dir()
    _rotate_alert_log()
    from datetime import datetime

    with open(_alert_log_path, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": datetime.now().isoformat(),
                    "agent_name": agent_name,
                    "slo_name": slo_name,
                    "current": current,
                    "threshold": threshold,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def notify_breach(agent_name: str, slo_name: str, current: float, threshold: float) -> None:
    """触发 SLO 违约通知（遍历已注册 handler）。"""
    report_slo_breach(agent_name, slo_name, current, threshold)
    # 写入日志文件
    _write_alert_file(agent_name, slo_name, current, threshold)
    # logger 兜底
    logger.warning("SLO Breach: %s %s = %s (threshold: %s)", agent_name, slo_name, current, threshold)
    # 遍历已注册 handler
    for handler in _alert_handlers:
        try:
            handler(agent_name, slo_name, current, threshold)
        except Exception:
            logger.exception("Alert handler failed for %s %s", agent_name, slo_name)
