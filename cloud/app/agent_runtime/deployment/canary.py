"""Agent 行为灰度发布 — 基于用户 hash 分流，支持双版本并行与自动回滚。"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from cloud.app.agent_runtime.core.shared_state import SharedStateEntry, get_shared_state

logger = logging.getLogger(__name__)

DEPLOYMENT_NAMESPACE = "deployment.canary"

ROLLOUT_STAGES = [0.1, 0.5, 1.0]


@dataclass
class CanaryConfig:
    name: str
    rollout_percentage: float = 0.1
    a_version: str = "stable"
    b_version: str = "canary"
    metric_thresholds: dict[str, float] = field(default_factory=lambda: {"error_rate": 0.05, "latency_p99": 5.0})
    metric_window_seconds: int = 300


class CanaryDeployment:
    """灰度发布管理器 — 按 user_id hash 分流至 A/B 版本，劣化时自动回滚。"""

    def __init__(self, config: CanaryConfig | None = None):
        """Initialize the canary deployment manager."""
        self._config = config or CanaryConfig(name="default")
        self._ss = get_shared_state()
        self._lock = threading.Lock()
        self._metrics: dict[str, list[dict[str, Any]]] = {}
        self._rollback_hooks: list[Callable] = []

    @property
    def config(self) -> CanaryConfig:
        """Return the current canary configuration."""
        return self._config

    def get_version_for_user(self, user_id: str) -> str:
        """Return the version (A or B) for the given user based on hash."""
        user_hash = self._hash_user(user_id)
        if user_hash < self._config.rollout_percentage:
            return self._config.b_version
        return self._config.a_version

    def set_rollout(self, percentage: float) -> None:
        """Set the rollout percentage for the canary version."""
        if not (0.0 <= percentage <= 1.0):
            raise ValueError(f"rollout_percentage must be between 0.0 and 1.0, got {percentage}")
        with self._lock:
            old = self._config.rollout_percentage
            self._config.rollout_percentage = percentage
        self._write_status("rollout_changed", {"old": old, "new": percentage})
        logger.info("CanaryDeployment: rollout changed %.0f%% -> %.0f%%", old * 100, percentage * 100)

    def promote_to_full(self) -> None:
        """Promote the canary version to 100% rollout."""
        self.set_rollout(1.0)
        self._write_status("promoted", {"version": self._config.b_version})
        logger.info("CanaryDeployment: %s promoted to 100%%", self._config.b_version)

    def record_metric(self, version: str, metric_name: str, value: float) -> None:
        """Record a metric for the given version."""
        with self._lock:
            self._metrics.setdefault(version, []).append(
                {"name": metric_name, "value": value, "timestamp": datetime.now().isoformat()},
            )

    def evaluate_health(self) -> dict[str, Any]:
        """Evaluate the health of both versions and auto-rollback if degraded."""
        now = datetime.utcnow()
        result: dict[str, Any] = {
            "healthy": True,
            "a_version": self._config.a_version,
            "b_version": self._config.b_version,
            "rollout_percentage": self._config.rollout_percentage,
            "violations": [],
        }

        for version in (self._config.a_version, self._config.b_version):
            with self._lock:
                recent = [
                    m
                    for m in self._metrics.get(version, [])
                    if (now - datetime.fromisoformat(m["timestamp"])).total_seconds() < self._config.metric_window_seconds
                ]
            for threshold_name, threshold_value in self._config.metric_thresholds.items():
                version_vals = [m["value"] for m in recent if m["name"] == threshold_name]
                if not version_vals:
                    continue
                avg_val = sum(version_vals) / len(version_vals)
                if avg_val > threshold_value:
                    result["healthy"] = False
                    result["violations"].append(
                        {
                            "version": version,
                            "metric": threshold_name,
                            "average": round(avg_val, 4),
                            "threshold": threshold_value,
                        },
                    )

        if not result["healthy"] and self._config.rollout_percentage > 0.0:
            self._auto_rollback(result["violations"])

        self._write_status("health_check", result)
        return result

    def register_rollback_hook(self, hook: Callable) -> None:
        """Register a callback to be invoked on auto-rollback."""
        with self._lock:
            self._rollback_hooks.append(hook)

    def _auto_rollback(self, violations: list[dict]) -> None:
        with self._lock:
            old = self._config.rollout_percentage
            self._config.rollout_percentage = 0.0
            logger.warning(
                "CanaryDeployment: auto-rollback from %.0f%% to 0%% violations=%s",
                old * 100,
                violations,
            )

        for hook in self._rollback_hooks:
            try:
                hook(violations)
            except Exception:
                logger.exception("CanaryDeployment: rollback hook failed")

        self._write_status(
            "auto_rollback",
            {
                "previous_rollout": old,
                "new_rollout": 0.0,
                "violations": violations,
            },
        )

    def _hash_user(self, user_id: str) -> float:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF

    def _write_status(self, event: str, payload: dict) -> None:
        self._ss.write(
            SharedStateEntry(
                namespace=DEPLOYMENT_NAMESPACE,
                key=f"{self._config.name}.{event}.{datetime.now().strftime('%Y%m%d%H%M%S')}",
                value={
                    "event": event,
                    "config_name": self._config.name,
                    "a_version": self._config.a_version,
                    "b_version": self._config.b_version,
                    "rollout_percentage": self._config.rollout_percentage,
                    "payload": payload,
                    "timestamp": datetime.now().isoformat(),
                },
                confidence=1.0,
                agent_key="canary_deployment",
                evidence=[f"CanaryDeployment: event={event} config={self._config.name}"],
            ),
        )

    def get_status(self) -> dict[str, Any]:
        """Return the current deployment status and recent events."""
        entries = self._ss.read(DEPLOYMENT_NAMESPACE, key=self._config.name)
        if not entries:
            return {
                "config_name": self._config.name,
                "a_version": self._config.a_version,
                "b_version": self._config.b_version,
                "rollout_percentage": self._config.rollout_percentage,
                "healthy": True,
                "events": [],
            }
        return {
            "config_name": self._config.name,
            "a_version": self._config.a_version,
            "b_version": self._config.b_version,
            "rollout_percentage": self._config.rollout_percentage,
            "healthy": True,
            "events": [e.value for e in entries[-10:]],
        }


def create_canary_deployment(
    name: str = "default",
    rollout_percentage: float = 0.1,
    a_version: str = "stable",
    b_version: str = "canary",
) -> CanaryDeployment:
    """Create and return a new canary deployment with the given configuration."""
    config = CanaryConfig(
        name=name,
        rollout_percentage=rollout_percentage,
        a_version=a_version,
        b_version=b_version,
    )
    deployment = CanaryDeployment(config=config)
    deployment._write_status("created", {"name": name, "rollout": rollout_percentage})
    logger.info("CanaryDeployment created: name=%s rollout=%.0f%%", name, rollout_percentage * 100)
    return deployment
