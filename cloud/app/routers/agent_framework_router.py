"""Agent 框架模板管理路由。"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.agent_ops.agent_framework_service import AgentFrameworkService
from shared.auth_scope import require_scope
from shared.base import success


class TemplateCreate(BaseModel):
    """TemplateCreate 服务类。"""

    template_key: str
    name: str = ""
    description: str = ""
    domain: str = "generic"
    capabilities: list[str] = []
    default_config: dict = {}
    triggers: list[str] = []
    endpoints: list[str] = []


class InstanceCreate(BaseModel):
    """InstanceCreate 服务类。"""

    instance_key: str
    template_key: str
    display_name: str = ""
    bind_to_end: str = "cloud"
    config_overrides: dict = {}


router = APIRouter(prefix="/agent/framework", tags=["Agent Framework"])


@router.get("/templates", summary="模板列表", description="按领域筛选Agent模板列表", tags=["Agent Framework"])
def list_templates(
    domain: str = Query(None),
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """list_templates 操作。

    Args:
        domain: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.list_templates(domain=domain))


@router.get("/templates/{template_key}", summary="查询模板", description="根据template_key获取模板详情", tags=["Agent Framework"])
def get_template(
    template_key: str,
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """get_template 操作。

    Args:
        template_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.get_template(template_key))


@router.post("/templates", status_code=status.HTTP_201_CREATED, summary="创建模板", description="创建一个新的Agent模板", tags=["Agent Framework"])
def create_template(
    body: TemplateCreate,
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """create_template 操作。

    Args:
        service: 描述
        _: 描述
    """
    return success(
        data=service.create_template(
            key=body.template_key,
            name=body.name,
            description=body.description,
            domain=body.domain,
            capabilities=body.capabilities,
            default_config=body.default_config,
            triggers=body.triggers,
            endpoints=body.endpoints,
        )
    )


@router.get("/instances", summary="实例列表", description="按状态和模板筛选实例列表", tags=["Agent Framework"])
def list_instances(
    status: str = Query(None),
    template_key: str = Query(None),
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """list_instances 操作。

    Args:
        status: 描述
        template_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.list_instances(status=status, template_key=template_key))


@router.get("/instances/{instance_key}", summary="查询实例", description="根据instance_key获取实例详情", tags=["Agent Framework"])
def get_instance(
    instance_key: str,
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """get_instance 操作。

    Args:
        instance_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.get_instance(instance_key))


@router.post(
    "/instances", status_code=status.HTTP_201_CREATED, summary="创建实例", description="基于模板创建一个新的Agent实例", tags=["Agent Framework"]
)
def create_instance(
    body: InstanceCreate,
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """create_instance 操作。

    Args:
        service: 描述
        _: 描述
    """
    return success(
        data=service.create_instance(
            instance_key=body.instance_key,
            template_key=body.template_key,
            display_name=body.display_name,
            bind_to_end=body.bind_to_end,
            config_overrides=body.config_overrides,
        )
    )


@router.post("/instances/{instance_key}/start", summary="启动实例", description="启动指定的Agent实例", tags=["Agent Framework"])
def start_instance(
    instance_key: str,
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """start_instance 操作。

    Args:
        instance_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.start_instance(instance_key))


@router.post("/instances/{instance_key}/stop", summary="停止实例", description="停止指定的Agent实例", tags=["Agent Framework"])
def stop_instance(
    instance_key: str,
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """stop_instance 操作。

    Args:
        instance_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.stop_instance(instance_key))


@router.post("/instances/{instance_key}/heartbeat", summary="实例心跳", description="发送Agent实例心跳", tags=["Agent Framework"])
def heartbeat_instance(
    instance_key: str,
    service: AgentFrameworkService = Depends(),
    _=Depends(require_scope(["pharma", "research"])),
):
    """heartbeat_instance 操作。

    Args:
        instance_key: 描述
        service: 描述
        _: 描述
    """
    return success(data=service.heartbeat_instance(instance_key))
