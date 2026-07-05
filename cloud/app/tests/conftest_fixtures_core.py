import os
import sqlite3 as _sql

import pytest
from starlette.testclient import TestClient

from shared.conftest_base import clean_test_tables, is_pg, setup_test_db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.path.join(BASE_DIR, "data", "test_cloud.db")
TEST_RESEARCH_DB = os.path.join(BASE_DIR, "data", "test_research.db")
os.makedirs(os.path.dirname(TEST_DB), exist_ok=True)


_AGENT_DDL = """
CREATE TABLE IF NOT EXISTS enforcement_log (id INTEGER PRIMARY KEY AUTOINCREMENT, rule_code TEXT, rule_name TEXT, severity TEXT, action TEXT, visit_data_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS research_enforcement_log (id INTEGER PRIMARY KEY AUTOINCREMENT, rule_code TEXT, rule_name TEXT, severity TEXT, action TEXT, visit_data_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS agent_execution_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT UNIQUE, source TEXT DEFAULT 'internal', session_id TEXT DEFAULT '', agent_role TEXT DEFAULT '', action_type TEXT DEFAULT 'process', input_data TEXT DEFAULT '{}', output_data TEXT DEFAULT '{}', status TEXT DEFAULT 'pending', retry_count INTEGER DEFAULT 0, max_retries INTEGER DEFAULT 3, result_verified INTEGER DEFAULT 0, verification_detail TEXT DEFAULT '', requires_human_approval INTEGER DEFAULT 0, assigned_to TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT, duration_ms INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS agent_runtime_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_key TEXT NOT NULL, goal TEXT NOT NULL, status TEXT DEFAULT 'pending', iterations INTEGER DEFAULT 0, tool_calls INTEGER DEFAULT 0, result TEXT, error_message TEXT, started_at TEXT, completed_at TEXT, log_detail TEXT DEFAULT '[]', created_at TEXT DEFAULT (datetime('now')), checkpoint_data TEXT DEFAULT NULL, trace_id TEXT DEFAULT '', cost_data TEXT DEFAULT '{}');
CREATE INDEX IF NOT EXISTS idx_runtime_logs_agent ON agent_runtime_logs(agent_key);
CREATE INDEX IF NOT EXISTS idx_runtime_logs_status ON agent_runtime_logs(status);
CREATE INDEX IF NOT EXISTS idx_runtime_logs_trace ON agent_runtime_logs(trace_id);
CREATE TABLE IF NOT EXISTS agent_runtime_approvals (id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT NOT NULL, agent_key TEXT NOT NULL, goal TEXT NOT NULL, step INTEGER DEFAULT 0, tool TEXT NOT NULL, params TEXT DEFAULT '{}', reasoning TEXT DEFAULT '', status TEXT DEFAULT 'pending', created_at TEXT DEFAULT (datetime('now')), responded_at TEXT, responded_by TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_approvals_status ON agent_runtime_approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_trace ON agent_runtime_approvals(trace_id);
CREATE TABLE IF NOT EXISTS agent_brains (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_key TEXT NOT NULL, user_id INTEGER DEFAULT 0, key TEXT NOT NULL, value TEXT NOT NULL, value_type TEXT DEFAULT 'str', updated_at TEXT DEFAULT (datetime('now')), UNIQUE(agent_key, user_id, key));
CREATE TABLE IF NOT EXISTS agent_state_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT NOT NULL, step_id INTEGER DEFAULT 0, plan_json TEXT DEFAULT '[]', results_json TEXT DEFAULT '[]', context_json TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'active');
CREATE INDEX IF NOT EXISTS idx_state_snapshots_agent ON agent_state_snapshots(agent_id);
CREATE INDEX IF NOT EXISTS idx_state_snapshots_status ON agent_state_snapshots(status);
CREATE TABLE IF NOT EXISTS agent_runtime_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT NOT NULL, step INTEGER NOT NULL, state_json TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_agent_runtime_snapshots_trace_step ON agent_runtime_snapshots(trace_id, step);
CREATE TABLE IF NOT EXISTS agent_traces (id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT NOT NULL UNIQUE, agent_name TEXT NOT NULL, user_id TEXT DEFAULT '', input_data TEXT DEFAULT '{}', output_data TEXT DEFAULT '{}', status TEXT DEFAULT 'running', total_duration_ms INTEGER DEFAULT 0, total_prompt_tokens INTEGER DEFAULT 0, total_completion_tokens INTEGER DEFAULT 0, total_cost REAL DEFAULT 0.0, tool_calls_json TEXT DEFAULT '[]', llm_calls_json TEXT DEFAULT '[]', started_at TEXT DEFAULT (datetime('now')), ended_at TEXT);
CREATE INDEX IF NOT EXISTS idx_agent_traces_trace_id ON agent_traces(trace_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_agent ON agent_traces(agent_name);
CREATE TABLE IF NOT EXISTS agent_cost_tracking (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT NOT NULL, model TEXT NOT NULL, model_tier TEXT DEFAULT 'cloud_normal', input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, cost REAL DEFAULT 0.0, trace_id TEXT DEFAULT '', timestamp TEXT DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS idx_cost_tracking_agent ON agent_cost_tracking(agent_name);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_model ON agent_cost_tracking(model);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_ts ON agent_cost_tracking(timestamp);
CREATE TABLE IF NOT EXISTS agent_eval_results (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT NOT NULL, trace_id TEXT NOT NULL, input_data TEXT DEFAULT '{}', output_data TEXT DEFAULT '{}', expected_data TEXT DEFAULT '{}', metrics_json TEXT DEFAULT '{}', passed INTEGER DEFAULT 0, score REAL DEFAULT 0.0, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS prompt_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT NOT NULL, version_id INTEGER NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now')), created_by TEXT DEFAULT 'system', UNIQUE(agent_name, version_id));
CREATE INDEX IF NOT EXISTS idx_prompt_versions_agent ON prompt_versions(agent_name);
"""


def _init_agent_tables():
    with _sql.connect(TEST_DB) as conn:
        conn.executescript(_AGENT_DDL)


@pytest.fixture(scope="session")
def app():
    import cloud.app.database as mod_db
    from cloud.app.schemas.ddl import SCHEMA_SQL

    setup_test_db(mod_db, SCHEMA_SQL, TEST_DB)
    _init_agent_tables()
    import cloud.app.research_database as mod_research

    mod_research.set_test_research_db_path(TEST_RESEARCH_DB)
    mod_research.init_research_db()

    if not is_pg():
        import sqlite3

        with sqlite3.connect(TEST_DB) as conn:
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("ALTER TABLE users ADD COLUMN updated_at TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass

    os.environ["RATE_LIMIT_DISABLE"] = "1"

    import cloud.app.services.agent_execution_service as aes

    aes.DB_PATH = TEST_DB

    import cloud.app.main as mod_main

    mod_main.DB_PATH = TEST_DB

    from cloud.app.main import app as _app

    return _app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_path():
    return TEST_DB


TABLES = [
    "user_team",
    "teams",
    "notifications",
    "notification_templates",
    "audit_logs",
    "board_tasks",
    "task_boards",
    "contents",
    "compliance_rules",
    "users",
    "enforcement_log",
]


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    clean_test_tables(TABLES)
