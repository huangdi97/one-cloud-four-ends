"""Registry mapping trigger names to agent configs and plan builders."""

TRIGGER_REGISTRY = {
    "anomaly_analysis": {
        "agent_key": "anomaly_analysis",
        "goal": "分析模式",
        "plan_builder": None,
    },
    "compliance_monitor": {
        "agent_key": "compliance_monitor",
        "goal": "",
        "plan_builder": "compliance_trigger.build_compliance_plan",
    },
    "suggestion_agent": {
        "agent_key": "suggestion_agent",
        "goal": "生成建议",
        "plan_builder": None,
    },
}


def get_plan_builder(name: str):
    """get plan builder."""
    entry = TRIGGER_REGISTRY[name]
    builder = entry["plan_builder"]
    if isinstance(builder, str):
        module_name, func_name = builder.rsplit(".", 1)
        mod = __import__(f"cloud.app.agent_runtime.{module_name}", fromlist=[func_name])
        func = getattr(mod, func_name)
        entry["plan_builder"] = func
        return func
    return builder
