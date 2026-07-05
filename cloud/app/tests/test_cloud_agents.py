"""Cloud agent smoke tests."""


def test_agent_role_service_imports():
    from cloud.app.services.agent_ops.agent_role_service import AgentRoleService

    assert AgentRoleService is not None


def test_agent_role_service_imports_and_instantiates():
    from cloud.app.services.agent_ops.agent_role_service import AgentRoleService

    service = AgentRoleService(db=None)

    assert isinstance(service, AgentRoleService)
