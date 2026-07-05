import json
from unittest import mock

from conftest_agentbench import Hypothesis, HypothesisEngine, Plan, PlanGenerator, PlanStep

from cloud.app.agent_runtime.core.loop_detector import LoopDetector
from cloud.app.agent_runtime.safety.cost_governor import CostGovernor

# ── CostGovernor Budget Intercept (2 tests) ──


def test_cost_governor_budget_sufficient():
    """CostGovernor: budget sufficient -> allow."""
    governor = CostGovernor(max_cost=100.0)
    result = governor.check("deepseek-chat", 500, 2048)
    assert result is True
    assert not governor.is_over_budget()


def test_cost_governor_budget_exceeded():
    """CostGovernor: budget exceeded -> block."""
    governor = CostGovernor(max_cost=1.0)
    governor.record_step_cost({"cost": 2.0, "model_tier": "cloud_normal"}, 0)
    assert governor.is_over_budget()
    result = governor.check("deepseek-chat", 100, 2048)
    assert result is False


# ── LoopDetector Loop Circuit Breaker (2 tests) ──


def test_loop_detector_simple():
    """LoopDetector: detect simple repeated pattern."""
    from cloud.app.agent_runtime.core.models import AgentDecision

    detector = LoopDetector()
    for _ in range(3):
        detector.record(AgentDecision(action="call_tool", tool="query_bidding", params={}))
    result = detector.detect()
    assert result is not None


def test_loop_detector_self_circuit_breaker():
    """LoopDetector: 3 self-loops trigger circuit breaker."""
    from cloud.app.agent_runtime.core.models import AgentDecision

    detector = LoopDetector()
    for _ in range(6):
        detector.record(AgentDecision(action="call_tool", tool="analyze_with_llm", params={"input": "loop"}))
    result = detector.detect()
    assert result is not None


# ── Analysis Hypothesis Verification Loop (3 tests) ──


@mock.patch("cloud.app.agent_runtime.analyzer.hypothesis.call_llm")
def test_analyzer_generate_hypotheses(mock_call_llm):
    """Analyzer: generate hypotheses from red light event."""
    mock_call_llm.return_value = json.dumps(
        [
            {"description": "拜访数据可能虚增", "confidence": 0.7, "type": "anomaly_pattern"},
            {"description": "经销商数据延迟上报", "confidence": 0.5, "type": "causal_relationship"},
        ]
    )
    analyzer = HypothesisEngine()
    event = {"event_id": "red-R001-1", "level": "L2", "evidence": {"visit_up": 0.4, "flow_down": -0.15}}
    hypotheses = analyzer.generate_hypotheses(event)
    assert len(hypotheses) >= 2
    for h in hypotheses:
        assert h.description
        assert h.status == "pending"


def test_analyzer_design_verification_plan():
    """Analyzer: design verification plan for a hypothesis."""
    analyzer = HypothesisEngine()
    hyp = Hypothesis(id="h1", description="拜访数据可能存在虚增", confidence=0.7, status="pending")
    plan = analyzer.design_verification_plan(hyp)
    assert plan.hypothesis_id == "h1"
    assert len(plan.checks) >= 1


@mock.patch("cloud.app.agent_runtime.analyzer.hypothesis.call_llm")
def test_analyzer_full_hypothesis_loop(mock_call_llm):
    """Analyzer: full hypothesis verification cycle returns narrative."""
    mock_call_llm.return_value = json.dumps(
        [
            {"description": "拜访数据可能虚增", "confidence": 0.7, "type": "anomaly_pattern"},
            {"description": "经销商数据延迟上报", "confidence": 0.5, "type": "causal_relationship"},
        ]
    )
    analyzer = HypothesisEngine()
    event = {"event_id": "red-R002-1", "level": "L2", "evidence": {"visit_up": 0.4, "flow_down": -0.15, "expense_up": 0.3}}
    result = analyzer.hypothesis_verification_loop(event)
    assert isinstance(result, dict)
    assert result.get("narrative")
    assert result["narrative"].root_cause
    assert len(result["narrative"].reasoning_chain) >= 1
    assert result["narrative"].confidence >= 0


# ── Compliance Trigger & Plan Validation (2 tests) ──


def test_compliance_trigger_build_plan():
    """Compliance trigger: build_compliance_plan generates 5-step structured plan."""
    from cloud.app.agent_runtime.core.compliance_trigger import build_compliance_plan

    plan = build_compliance_plan("test task", {"rep_id": "R001"})
    assert len(plan) == 5
    step_actions = [s["action"] for s in plan]
    assert step_actions == ["verify_expense", "verify_visit", "trace_distribution", "holographic_audit_check", "complete"]


def test_plan_validation_dependency_check():
    """Plan validation: dependency integrity check fails for missing deps."""
    plan = Plan(
        goal="test",
        steps=[
            PlanStep(step_id="s1", description="step 1", tool="tool_a", dependencies=["s2"]),
            PlanStep(step_id="s2", description="step 2", tool="tool_b", dependencies=[]),
        ],
        max_steps=10,
        plan_confidence=0.5,
    )
    assert PlanGenerator().validate_plan(plan)

    bad_plan = Plan(
        goal="test",
        steps=[
            PlanStep(step_id="s1", description="step 1", tool="tool_a", dependencies=["s3"]),
        ],
        max_steps=10,
        plan_confidence=0.5,
    )
    assert not PlanGenerator().validate_plan(bad_plan)
