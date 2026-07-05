import pytest
from conftest_agentbench import _assert_schema, _case_ids, _load_cases, _memory_db

from cloud.app.agent_runtime.core.agent_specs import AGENT_SPECS
from cloud.app.agent_runtime.core.planner import Plan, PlanGenerator
from cloud.app.agent_runtime.safety.verifier import Verifier
from cloud.app.compliance.engine import ComplianceEnforcer

# ── Golden Tests (3) ──


@pytest.mark.parametrize("case", _load_cases("compliance_cases.json"), ids=_case_ids("compliance_cases.json"))
def test_compliance_golden(case):
    db = _memory_db()
    try:
        result = ComplianceEnforcer(db).check_visit(case["input"])
    finally:
        db.close()

    actual_action = "block" if result else "pass"
    expected_action = case["expected"]["action"]
    assert actual_action == expected_action, f"{case['name']}: expected action {expected_action}, got {actual_action}"

    actual_rule_names = [violation.rule_name for violation in result]
    expected_rule_names = case["expected"].get("rule_names", [])
    assert actual_rule_names == expected_rule_names, f"{case['name']}: expected rule_names {expected_rule_names}, got {actual_rule_names}"


@pytest.mark.parametrize("case", _load_cases("pipeline_cases.json"), ids=_case_ids("pipeline_cases.json"))
def test_pipeline_golden(case):
    plan = Plan(**case["plan"])
    assert PlanGenerator().validate_plan(plan), f"{case['name']}: plan failed validation"
    assert plan.goal == case["input"], f"{case['name']}: input goal and plan goal differ"

    actual_tools = {step.tool for step in plan.steps}
    expected_tools = set(case["expected_tools"])
    missing_tools = sorted(expected_tools - actual_tools)
    assert not missing_tools, f"{case['name']}: missing expected tools {missing_tools}"

    expected_count = case["expected_plan_count"]
    actual_count = len(plan.steps)
    assert expected_count["min"] <= actual_count <= expected_count["max"], (
        f"{case['name']}: expected plan count in {expected_count}, got {actual_count}"
    )


@pytest.mark.parametrize(
    "case",
    _load_cases("response_format_cases.json"),
    ids=_case_ids("response_format_cases.json"),
)
def test_response_format_golden(case):
    assert "sample_input" in case, f"{case['name']}: missing sample_input"
    _assert_schema(case["sample_output"], case["schema"])


# ── L4 Compliance Tests (5) ──


def test_compliance_l4_normal_flow():
    """Compliance L4 normal flow: trigger -> plan -> verify -> complete."""
    spec = AGENT_SPECS.get("compliance_monitor")
    assert spec is not None, "compliance_monitor agent spec must exist"
    assert "trigger_mode" in spec and spec["trigger_mode"] == "l4"
    assert len(spec.get("trigger_plan_steps", [])) >= 4
    tools = set(spec["allowed_tools"])
    for step in spec["trigger_plan_steps"]:
        if step["tool"] != "complete":
            assert step["tool"] in tools, f"trigger step tool {step['tool']} not in allowed_tools"


def test_compliance_l4_red_light_trigger():
    """Compliance L4 red light trigger: holographic audit with score >= 0.8 triggers red_light."""
    from cloud.app.compliance.holographic_audit import HolographicAuditEngine

    engine = HolographicAuditEngine()
    result = engine.check(
        expense_data=[{"expense": 1000, "trend": "up"}],
        visit_data=[{"visit_count": 50, "trend": "up"}],
        distribution_data=[{"flow": 10, "trend": "down"}],
    )
    assert result.decision == "trigger_red_light"
    assert result.confidence_score >= 0.8
    assert result.suspicion_level == "high"


def test_compliance_l4_degrade_fallback():
    """Compliance L4: when holographic audit fails, fallback to individual checks and degrade gracefully."""
    from cloud.app.compliance.holographic_audit import HolographicAuditEngine

    engine = HolographicAuditEngine()
    result = engine.check(
        expense_data=None,
        visit_data=[{"visit_count": 10, "trend": "flat"}],
        distribution_data=None,
    )
    assert result.passed
    assert result.confidence_score >= 0


def test_compliance_l4_timeout():
    """Compliance L4 timeout: verify spec max_iterations is bounded."""
    spec = AGENT_SPECS.get("compliance_monitor")
    assert spec["max_iterations"] <= 10
    assert spec.get("max_retries", 0) >= 1


def test_compliance_l4_tool_failure():
    """Compliance L4 tool failure: verifier rejects a failed tool call."""
    verifier = Verifier()
    with pytest.raises(ValueError, match="permission denied"):
        verifier.verify({"success": False, "error": "permission denied"})
