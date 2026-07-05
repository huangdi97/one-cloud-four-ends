"""Agent 交叉验证链 — 定义 Agent 间级联链路。

链路定义: compliance.red_light → anomaly_analysis 验证 → sales_suggestion 补救建议

使用 SharedState namespace 作为通信载体，不直接 Agent-to-Agent 通信。
"""

import logging
import threading
from datetime import datetime
from typing import Any

from cloud.app.agent_runtime.core.agent_registry import AgentRegistry
from cloud.app.agent_runtime.core.shared_state import SharedStateEntry, get_shared_state

logger = logging.getLogger(__name__)

CASCADE_HEALTH_NAMESPACE = "cascade.health"
CASCADE_UNRELIABLE_THRESHOLD = 0.3


class CascadeMonitor:
    """级联链路置信度监控 — 跟踪链上每步 confidence 并计算累积置信度。"""

    def __init__(self):
        self._ss = get_shared_state()
        self._lock = threading.Lock()
        self._chain_steps: dict[str, list[dict[str, Any]]] = {}

    def record_step(self, entry: SharedStateEntry) -> None:
        """Record a cascade step, update cumulative confidence, and alert if below threshold."""
        chain_id = self._resolve_chain_id(entry)
        step_info = {
            "namespace": entry.namespace,
            "key": entry.key,
            "confidence": entry.confidence,
            "agent_key": entry.agent_key,
            "timestamp": entry.timestamp or datetime.now().isoformat(),
        }
        with self._lock:
            self._chain_steps.setdefault(chain_id, []).append(step_info)
            steps = self._chain_steps[chain_id]
            cumulative = 1.0
            for s in steps:
                cumulative *= s["confidence"]

        self._write_health(chain_id, steps, cumulative)

        if cumulative < CASCADE_UNRELIABLE_THRESHOLD:
            self._raise_alert(chain_id, cumulative, steps)

    def get_chain_health(self, chain_id: str) -> dict[str, Any] | None:
        """Read the latest health record for a given cascade chain."""
        results = self._ss.read(CASCADE_HEALTH_NAMESPACE, key=chain_id)
        if not results:
            return None
        return results[-1].value

    def _resolve_chain_id(self, entry: SharedStateEntry) -> str:
        if entry.namespace.startswith("compliance."):
            return "compliance_anomaly_sales"
        if entry.namespace.startswith("analysis."):
            return "anomaly_sales"
        if entry.namespace.startswith("cross_validation."):
            return "cross_validation"
        return f"chain_{entry.namespace.replace('.', '_')}"

    def _write_health(self, chain_id: str, steps: list[dict], cumulative: float) -> None:
        health_value = {
            "chain_id": chain_id,
            "step_count": len(steps),
            "cumulative_confidence": round(cumulative, 4),
            "steps": steps,
            "healthy": cumulative >= CASCADE_UNRELIABLE_THRESHOLD,
            "last_updated": datetime.now().isoformat(),
        }
        self._ss.write(
            SharedStateEntry(
                namespace=CASCADE_HEALTH_NAMESPACE,
                key=chain_id,
                value=health_value,
                confidence=min(cumulative, 1.0),
                agent_key="cascade_monitor",
                evidence=[f"CascadeMonitor: chain={chain_id} cumulative={cumulative:.4f}"],
            ),
        )

    def _raise_alert(self, chain_id: str, cumulative: float, steps: list[dict]) -> None:
        alert_value = {
            "alert_type": "cascade_unreliable",
            "chain_id": chain_id,
            "cumulative_confidence": round(cumulative, 4),
            "threshold": CASCADE_UNRELIABLE_THRESHOLD,
            "step_count": len(steps),
            "last_step": steps[-1] if steps else None,
            "timestamp": datetime.now().isoformat(),
            "message": f"级联链路 {chain_id} 累积置信度 {cumulative:.4f} 低于阈值 {CASCADE_UNRELIABLE_THRESHOLD}，标记为 unreliable",
        }
        self._ss.write(
            SharedStateEntry(
                namespace="cascade.alert",
                key=f"unreliable_{chain_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                value=alert_value,
                confidence=cumulative,
                agent_key="cascade_monitor",
                evidence=[f"CascadeMonitor: ALERT chain={chain_id} cumulative={cumulative:.4f} < threshold"],
            ),
        )
        logger.warning("CascadeMonitor ALERT: %s cumulative=%.4f", chain_id, cumulative)


class CrossValidationChain:
    """Agent 交叉验证链 — 在 namespace 事件触发后判断是否启动级联链路。"""

    CHAINS = [
        {
            "source_namespace": "compliance.result",
            "source_agent": "compliance_monitor",
            "target_agent": "anomaly_analysis",
            "transformer": "compliance_to_analysis",
            "description": "合规红灯 → 根因分析验证",
        },
        {
            "source_namespace": "analysis.result",
            "source_agent": "anomaly_analysis",
            "target_agent": "sales_suggestion",
            "transformer": "analysis_to_suggestion",
            "description": "根因分析结论 → 销售补救建议",
        },
    ]

    def __init__(self, db=None):
        self._db = db
        self._ss = get_shared_state()
        self._cascade_monitor = CascadeMonitor()

    @property
    def cascade_monitor(self) -> CascadeMonitor:
        """Return the shared CascadeMonitor instance used to track chain health."""
        return self._cascade_monitor

    def evaluate_chain(self, entry: SharedStateEntry) -> list[dict]:
        """检查 entry 是否匹配某条链的 source_namespace，匹配则返回链式触发指令列表。

        Returns:
            [{"target_agent": str, "goal": str, "source_evidence": list}, ...]
        """
        triggers = []
        for chain in self.CHAINS:
            if entry.namespace.startswith(chain["source_namespace"]):
                source_evidence = self._build_source_evidence(entry, chain)
                goal = self._build_goal(entry, chain)
                triggers.append(
                    {
                        "target_agent": chain["target_agent"],
                        "goal": goal,
                        "source_evidence": source_evidence,
                        "chain_desc": chain["description"],
                    }
                )
                logger.info(
                    "CrossValidationChain: %s → %s (namespace=%s)",
                    chain["source_agent"],
                    chain["target_agent"],
                    entry.namespace,
                )
        return triggers

    def execute_chain(self, entry: SharedStateEntry) -> None:
        """执行交叉验证链：将源 entry 的证据写入 SharedState 通信 namespace，
        然后触发目标 Agent 的队列调度。

        链式触发不直接调用 Agent，而是通过 SharedState 写入，
        再由 NamespaceEventBus 的 event_subscriptions 匹配触发目标 Agent。
        """
        self._cascade_monitor.record_step(entry)

        triggers = self.evaluate_chain(entry)
        if not triggers:
            return

        for t in triggers:
            target_agent = t["target_agent"]
            agent = AgentRegistry.get(target_agent)
            if not agent:
                logger.warning("CrossValidationChain: target agent '%s' not found", target_agent)
                continue

            communication_value = {
                "source_agent": entry.agent_key,
                "source_namespace": entry.namespace,
                "source_evidence": t["source_evidence"],
                "triggered_at": datetime.now().isoformat(),
                "chain_desc": t["chain_desc"],
            }

            comm_ns = f"cross_validation.{target_agent}"
            self._ss.write(
                SharedStateEntry(
                    namespace=comm_ns,
                    key=f"incoming_{entry.agent_key}_{entry.key}",
                    value=communication_value,
                    confidence=1.0,
                    agent_key="cross_validation_chain",
                    evidence=[
                        f"来源: CrossValidationChain({t['chain_desc']})",
                        f"触发: {entry.agent_key} → {target_agent}",
                        f"命名空间: {entry.namespace}",
                    ],
                ),
            )
            logger.info(
                "CrossValidationChain: wrote to %s for agent=%s chain=%s",
                comm_ns,
                target_agent,
                t["chain_desc"],
            )

            self._enqueue_agent(target_agent, entry, t)

    def _build_source_evidence(self, entry: SharedStateEntry, chain: dict) -> list[str]:
        """根据链路类型构建 source_evidence。"""
        evidence = [
            f"来源链: {chain['description']}",
            f"源 Agent: {chain['source_agent']}",
            f"源 namespace: {entry.namespace}",
        ]
        if entry.evidence:
            evidence.extend(entry.evidence[:3])
        if isinstance(entry.value, dict):
            for k in ["summary", "result", "conclusion", "analysis"]:
                if k in entry.value:
                    evidence.append(f"内容: {entry.value[k]}")
                    break
            else:
                evidence.append(f"内容: {str(entry.value)[:200]}")
        return evidence

    def _build_goal(self, entry: SharedStateEntry, chain: dict) -> str:
        """根据链路类型构建目标 Agent 的执行目标。"""
        desc = chain["description"]
        value_summary = ""
        if isinstance(entry.value, dict):
            value_summary = entry.value.get("summary", str(entry.value)[:100])
        return f"交叉验证链触发: {desc} | 来源: {entry.namespace}.{entry.key} | {value_summary}"

    def _enqueue_agent(self, agent_key: str, entry: SharedStateEntry, trigger: dict) -> None:
        """将目标 Agent 入队等待执行。"""
        if not self._db:
            logger.warning("CrossValidationChain: no db connection, cannot enqueue %s", agent_key)
            return
        try:
            from cloud.app.agent_runtime.core.queue_manager import AgentQueueManager

            qm = AgentQueueManager(self._db)
            scheduled_at = datetime.now().isoformat()
            qm.enqueue(agent_key, trigger["goal"], scheduled_at)
            logger.info("CrossValidationChain: enqueued %s via chain trigger", agent_key)
        except Exception:
            logger.exception("CrossValidationChain: failed to enqueue %s", agent_key)
