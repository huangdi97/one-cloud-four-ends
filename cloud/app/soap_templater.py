"""SOAP 模板处理函数。"""

from typing import Optional

from fastapi import Depends

from cloud.app.services.rep_workbench.soap_decision_service import SoapDecisionService
from cloud.app.soap_validator import TemplateCreate
from shared.auth_scope import require_scope
from shared.base import success


def create_template(
    body: TemplateCreate,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(
        service.create_template(
            name=body.name,
            category=body.category,
            description=body.description,
            structure=body.structure,
            created_by=cu["user_id"],
        )
    )


def list_templates(
    category: Optional[str] = None,
    cu=Depends(require_scope("visit")),
    service: SoapDecisionService = Depends(),
):
    return success(service.list_templates(category=category))
