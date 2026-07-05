"""世界模型后台循环 — 定时 + 事件驱动认知引擎。
读所有 namespace，输出模式认知到 shared.cognition.*。
不是 Agent，不调工具。
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime

from cloud.app.agent_runtime.core.shared_state import SharedStateEntry, get_shared_state

logger = logging.getLogger(__name__)


class WorldModelLoop:
    """后台认知循环：定时（每 6h）+ namespace 变更事件增量触发。纯 LLM 推理，不调工具。"""

    COGNITION_NAMESPACE = "shared.cognition"
    DEFAULT_INTERVAL_SECONDS = 6 * 3600
    COGNITION_TTL_DAYS = 7

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_full_scan: float = 0.0
        self._changed_since_last: list[str] = []

    def start(self) -> None:
        """启动后台循环线程。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="world-model")
        self._thread.start()
        ss = get_shared_state()
        ss.subscribe(self._on_namespace_change)
        logger.info("WorldModelLoop started")

    def stop(self) -> None:
        """停止后台循环线程。"""
        self._running = False

    def _on_namespace_change(self, entry: SharedStateEntry) -> None:
        """Events: track changed namespaces for incremental scan."""
        ns = entry.namespace
        if not ns.startswith("shared."):
            if ns not in self._changed_since_last:
                self._changed_since_last.append(ns)

    def _run_loop(self) -> None:
        """Main loop: full scan every 6h, incremental on events."""
        while self._running:
            now = time.time()
            if now - self._last_full_scan >= self.DEFAULT_INTERVAL_SECONDS:
                self._full_scan()
                self._last_full_scan = now
            elif self._changed_since_last:
                namespaces = list(self._changed_since_last)
                self._changed_since_last.clear()
                self._incremental_scan(namespaces)
            self._cleanup_expired()
            time.sleep(60)

    def _full_scan(self) -> None:
        """Full scan: read all namespaces, find cross-domain patterns."""
        logger.info("WorldModel full scan starting")
        ss = get_shared_state()
        all_namespaces = self._collect_all_namespaces(ss)
        if not all_namespaces:
            logger.info("WorldModel full scan: no namespaces found")
            return
        cognitions = self._llm_reason(all_namespaces)
        for cognition in cognitions:
            self._write_cognition(ss, cognition)
        logger.info("WorldModel full scan complete: %d cognitions", len(cognitions))

    def _incremental_scan(self, namespaces: list[str]) -> None:
        """Incremental scan on specific namespace changes."""
        logger.info("WorldModel incremental scan for: %s", namespaces)
        ss = get_shared_state()
        snapshot = {}
        for ns in namespaces:
            entries = ss.read(ns, min_confidence=0.3)
            if entries:
                snapshot[ns] = [e.value for e in entries[-5:]]
        if not snapshot:
            return
        cognitions = self._llm_reason(snapshot, incremental=True)
        for cognition in cognitions:
            self._write_cognition(ss, cognition)
        logger.info("WorldModel incremental scan complete: %d cognitions", len(cognitions))

    @staticmethod
    def _collect_all_namespaces(ss) -> dict:
        try:
            return ss.list_all_namespaces()
        except AttributeError:
            return {}

    def _llm_reason(self, snapshot: dict, incremental: bool = False) -> list[dict]:
        """LLM 推理：找跨域模式、关联、趋势。"""
        domains = list(snapshot.keys())
        if len(domains) < 1:
            return []
        domain_summary = {}
        for ns, values in snapshot.items():
            sample = values[:3]
            summary = "; ".join(str(v)[:200] for v in sample)
            domain_summary[ns] = summary

        prompt = self._build_prompt(domain_summary, incremental)
        try:
            from cloud.app.agent_runtime.runtime_llm import RuntimeLLM

            llm = RuntimeLLM()
            msg = [{"role": "user", "content": prompt}]
            result = llm._call_ai(msg, temperature=0.3, force_level=2)
            reply = result.get("reply", "")
            parsed = self._parse_llm_output(reply, domains)
            return parsed
        except Exception:
            logger.exception("WorldModel LLM reasoning failed")
            return []

    @staticmethod
    def _build_prompt(domain_summary: dict, incremental: bool) -> str:
        ns_lines = "\n".join(f"  {ns}: {summary}" for ns, summary in domain_summary.items())
        mode = "增量分析" if incremental else "全量分析"
        return (
            f"你是一个世界模型认知引擎，负责从多领域数据中发现跨域模式、异常关联和趋势。\n"
            f"当前模式：{mode}\n\n"
            f"各 namespace 数据摘要：\n{ns_lines}\n\n"
            "请分析上述数据，找出跨域模式、异常关联或重要趋势。\n"
            "回复 JSON 数组，每个元素包含：\n"
            "  - pattern: 模式名称\n"
            "  - description: 模式描述\n"
            "  - confidence: 置信度 0-1\n"
            "  - source_namespaces: 涉及的 namespace 数组\n"
            f"  - agent_keys: 关联的 Agent key 数组（从 namespace 名推断）\n"
            "Reply ONLY a valid JSON array."
        )

    @staticmethod
    def _parse_llm_output(reply: str, domains: list[str]) -> list[dict]:
        """Parse LLM JSON output into cognition entries."""
        reply = reply.strip()
        if reply.startswith("```"):
            reply = reply.split("\n", 1)[-1]
            reply = reply.rsplit("```", 1)[0]
        try:
            items = json.loads(reply)
            if not isinstance(items, list):
                items = [items]
        except (json.JSONDecodeError, TypeError):
            logger.warning("WorldModel LLM output parse failed: %s", reply[:100])
            return []
        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            results.append(WorldModelLoop._build_pattern_entry(item, domains))
        return results

    @staticmethod
    def _build_pattern_entry(item, domains):
        return {
            "pattern": item.get("pattern", "未知模式"),
            "description": item.get("description", ""),
            "confidence": float(item.get("confidence", 0.5)),
            "source_namespaces": item.get("source_namespaces", domains),
            "agent_keys": item.get("agent_keys", []),
        }

    @staticmethod
    def _write_cognition(ss, cognition: dict) -> None:
        """Write cognition to shared.cognition namespace."""
        entry = SharedStateEntry(
            namespace=WorldModelLoop.COGNITION_NAMESPACE,
            key=f"cog_{uuid.uuid4().hex[:12]}",
            value={
                "pattern": cognition.get("pattern", ""),
                "description": cognition.get("description", ""),
                "confidence": cognition.get("confidence", 0.5),
                "source_namespaces": cognition.get("source_namespaces", []),
                "agent_keys": cognition.get("agent_keys", []),
            },
            agent_key="world_model",
            confidence=cognition.get("confidence", 0.5),
            evidence=[f"source:{ns}" for ns in cognition.get("source_namespaces", [])],
        )
        ss.write(entry, caller_agent_key="world_model")
        logger.info("Cognition written: pattern=%s confidence=%.2f", cognition.get("pattern", ""), cognition.get("confidence", 0.5))

    def _cleanup_expired(self) -> None:
        """Remove cognitions older than COGNITION_TTL_DAYS with low confidence."""
        ss = get_shared_state()
        entries = ss.read(self.COGNITION_NAMESPACE, min_confidence=0.0)
        now = time.time()
        removed = 0
        for entry in entries:
            if entry.confidence < 0.4 and entry.timestamp:
                if self._prune_expired_entry(entry, now):
                    removed += 1
        if removed:
            logger.info("WorldModel cleanup: removed %d expired cognitions", removed)

    def _prune_expired_entry(self, entry, now):
        try:
            ts = datetime.fromisoformat(entry.timestamp).timestamp()
            if now - ts > self.COGNITION_TTL_DAYS * 86400:
                try:
                    ss = get_shared_state()
                    ss._entries.remove(entry)
                    return True
                except ValueError:
                    pass
        except (ValueError, TypeError):
            pass
        return False


_global_world_model: WorldModelLoop | None = None
_wm_lock = threading.Lock()


def get_world_model() -> WorldModelLoop:
    """获取全局 WorldModelLoop 单例。"""
    global _global_world_model
    if _global_world_model is None:
        with _wm_lock:
            if _global_world_model is None:
                _global_world_model = WorldModelLoop()
    return _global_world_model
