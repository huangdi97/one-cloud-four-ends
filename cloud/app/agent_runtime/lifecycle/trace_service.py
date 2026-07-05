"""Trace service layer — encapsulates query, search, evaluation, and audit logic."""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from cloud.app.agent_runtime.core.secret_manager import SecretManager
from cloud.app.agent_runtime.lifecycle.tracer import AgentTracer
from cloud.app.agent_runtime.reflection.evaluator import AgentEvaluator
from cloud.app.database import DB_PATH

BIOPULSE_AUDIT_LOG = os.environ.get("BIOPULSE_AUDIT_LOG", "data/biopulse_audit.log")


class TraceService:
    """Service layer for trace query, search, evaluation, audit, and secret management."""

    def __init__(self):
        self._tracer: AgentTracer | None = None
        self._secret_manager: SecretManager | None = None

    def get_tracer(self) -> AgentTracer:
        """Lazy-init and return the AgentTracer instance."""
        if self._tracer is None:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            self._tracer = AgentTracer(conn)
        return self._tracer

    def _get_secret_manager(self) -> SecretManager:
        if self._secret_manager is None:
            self._secret_manager = SecretManager()
        return self._secret_manager

    def _get_audit_logger(self) -> logging.Logger:
        logger = logging.getLogger("biopulse-audit")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            log_dir = os.path.dirname(BIOPULSE_AUDIT_LOG)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            handler = logging.FileHandler(BIOPULSE_AUDIT_LOG, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
            logger.propagate = False
        return logger

    def get_trace(self, trace_id: str) -> dict | None:
        """Retrieve a single trace by ID."""
        return self.get_tracer().get_trace(trace_id)

    def list_traces(self, agent_name: str | None = None, page: int = 1, page_size: int = 20) -> dict:
        """List traces, optionally filtered by agent name, with pagination."""
        return self.get_tracer().list_traces(agent_name=agent_name, page=page, page_size=page_size)

    def get_metrics_summary(self) -> dict:
        """Return a summary of aggregate trace metrics."""
        return self.get_tracer().get_metrics_summary()

    def get_eval_dashboard(self) -> dict:
        """Return the evaluation dashboard data from the AgentEvaluator."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            evaluator = AgentEvaluator(conn)
            return evaluator.get_dashboard()
        finally:
            conn.close()

    def list_recoverable(self) -> list[dict]:
        """List all recoverable (checkpointed) execution snapshots."""
        from cloud.app.agent_runtime.memory.state_snapshot import recover as recover_fn

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            snapshots = recover_fn(conn)
            result = []
            for snap in snapshots:
                state = snap.get("state", {})
                result.append(
                    {
                        "trace_id": snap.get("trace_id", ""),
                        "agent_key": state.get("agent_key", ""),
                        "goal": state.get("goal", ""),
                        "step": snap.get("step", 0),
                        "created_at": snap.get("created_at", ""),
                    }
                )
            return result
        finally:
            conn.close()

    def resume_checkpoint(self, trace_id: str, auth_header: str) -> dict | None:
        """Resume execution from the latest checkpoint for the given trace."""
        import sqlite3

        from cloud.app.agent_runtime.memory.state_snapshot import load_latest_snapshot

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            snap = load_latest_snapshot(conn, trace_id)
            if not snap:
                return None
            state = snap.get("state", {})
            agent_key = state.get("agent_key", "")
            goal = state.get("goal", "")
            if not agent_key or not goal:
                return None
            from cloud.app.agent_runtime.core.runtime_core import RuntimeCore

            runtime = RuntimeCore(conn, conn, auth_header, agent_key)
            result = runtime.execute(goal, agent_key, state.get("context", {}))
            return result.model_dump()
        finally:
            conn.close()

    def list_secrets(self) -> list[dict]:
        """List all stored secret keys."""
        return self._get_secret_manager().export_keys()

    def set_secret(self, key_name: str, value: str) -> dict:
        """Set or update a secret by key name."""
        sm = self._get_secret_manager()
        sm.set(key_name, value)
        return {"key_name": key_name, "updated": True}

    def delete_secret(self, key_name: str) -> dict:
        """Delete a secret by key name."""
        self._get_secret_manager().delete(key_name)
        return {"key_name": key_name, "deleted": True}

    def log_agent_decision(
        self,
        agent_name: str,
        input_summary: str,
        decisions: list,
        risk_level: str,
        approval_status: str,
        human_reviewer: str = "",
    ) -> None:
        """Log an agent decision to the audit log, with an extra auto-audit entry for high risk."""
        record = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "agent_name": agent_name,
            "input_summary": input_summary,
            "decisions": decisions,
            "risk_level": risk_level,
            "approval_status": approval_status,
            "human_reviewer": human_reviewer,
        }
        self._get_audit_logger().info(json.dumps(record, ensure_ascii=False))

        if risk_level == "high":
            auto_record = {
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "agent_name": agent_name,
                "input_summary": input_summary,
                "decisions": decisions,
                "risk_level": risk_level,
                "approval_status": approval_status,
                "human_reviewer": human_reviewer,
                "auto_audit": True,
                "auto_audit_reason": "high_risk",
            }
            self._get_audit_logger().info(json.dumps(auto_record, ensure_ascii=False))

    def get_agent_decisions(
        self,
        agent_name: str | None = None,
        risk_level: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve agent decision audit records with optional filters."""
        log_file = Path(BIOPULSE_AUDIT_LOG)
        if not log_file.exists():
            return []

        records: list[dict[str, Any]] = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if agent_name and record.get("agent_name") != agent_name:
                    continue
                if risk_level and record.get("risk_level") != risk_level:
                    continue
                if date_from and record.get("timestamp", "") < date_from:
                    continue
                if date_to and record.get("timestamp", "") > date_to:
                    continue
                records.append(record)

        records.reverse()
        return records[:limit]

    def auto_audit_decision(
        self,
        agent_name: str,
        input_summary: str,
        decisions: list,
        risk_level: str,
    ) -> None:
        """Log an auto-audited decision with approval_status set to auto_audited."""
        self.log_agent_decision(
            agent_name=agent_name,
            input_summary=input_summary,
            decisions=decisions,
            risk_level=risk_level,
            approval_status="auto_audited",
            human_reviewer="system",
        )
