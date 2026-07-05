from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette import status

from cloud.app.services.rep_workbench.content_factory_service import ContentFactoryService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/content-factory", tags=["内容工厂"])


class CreateTemplateRequest(BaseModel):
    template_key: str
    name: str = ""
    content_type: str = "text"
    template_body: str = ""
    compliance_rules: str = "[]"
    variables: str = "{}"


class RenderRequest(BaseModel):
    template_key: str
    variables: dict = {}


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建模板", description="创建新的内容模板", tags=["内容工厂"])
def create_template(
    body: CreateTemplateRequest,
    current_user: dict = Depends(require_scope("visit")),
    service: ContentFactoryService = Depends(),
) -> Any:
    result = service.create_template(
        template_key=body.template_key,
        name=body.name,
        content_type=body.content_type,
        template_body=body.template_body,
        compliance_rules=body.compliance_rules,
        variables=body.variables,
    )
    return success(data=result)


@router.post("/render", summary="渲染模板", description="渲染内容模板并执行合规检查", tags=["内容工厂"])
def render_template(
    body: RenderRequest,
    current_user: dict = Depends(require_scope("visit")),
    service: ContentFactoryService = Depends(),
) -> Any:
    result = service.render(
        template_key=body.template_key,
        variables=body.variables,
    )
    return success(data=result)


@router.get("", summary="模板列表", description="列出所有可用的内容模板", tags=["内容工厂"])
def list_templates(
    current_user: dict = Depends(require_scope("visit")),
    service: ContentFactoryService = Depends(),
) -> Any:
    return success(data=service.list_templates())
