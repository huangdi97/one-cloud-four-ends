"""MDT smoke tests."""


def test_mdt_engine_service_imports():
    from cloud.app.services.collab.mdt_engine_service import MdtEngineService

    assert MdtEngineService is not None


def test_mdt_engine_service_imports_and_instantiates():
    from cloud.app.services.collab.mdt_engine_service import MdtEngineService

    service = MdtEngineService(db=None)

    assert isinstance(service, MdtEngineService)
