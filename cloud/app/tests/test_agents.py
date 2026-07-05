"""Agent package smoke tests."""

import sys
import types


def _install_langgraph_stub():
    if "langgraph.graph" in sys.modules:
        return
    langgraph_module = types.ModuleType("langgraph")
    graph_module = types.ModuleType("langgraph.graph")

    class StateGraph:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    graph_module.END = "__END__"
    graph_module.StateGraph = StateGraph
    sys.modules.setdefault("langgraph", langgraph_module)
    sys.modules.setdefault("langgraph.graph", graph_module)


def test_agent_pipeline_service_imports():
    _install_langgraph_stub()
    from cloud.app.services.agent_ops.agent_pipeline_service import AgentPipelineService

    assert AgentPipelineService is not None


def test_agent_pipeline_service_imports_and_instantiates():
    _install_langgraph_stub()
    from cloud.app.services.agent_ops.agent_pipeline_service import AgentPipelineService

    service = AgentPipelineService(db=None)

    assert isinstance(service, AgentPipelineService)
