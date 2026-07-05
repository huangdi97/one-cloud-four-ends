"""21 CFR Part 11 compliance APIs."""

from fastapi import APIRouter, Depends

from cloud.app.schemas.part11_compliance import SignDocumentRequest
from cloud.app.services.compliance_svc.part11_compliance_service import (
    get_audit_trail,
    sign_document,
    verify_signature,
)
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/part11", tags=["21 CFR Part 11"])


@router.post("/sign", tags=["21 CFR Part 11"])
def part11_sign(body: SignDocumentRequest, _: dict = Depends(require_scope(["pharma", "research"]))):
    return success(data=sign_document(body.user_id, body.document_id, body.password))


@router.get("/audit/{document_id}", tags=["21 CFR Part 11"])
def part11_audit(document_id: str):
    return success(data=get_audit_trail(document_id))


@router.get("/verify/{signature_id}", tags=["21 CFR Part 11"])
def part11_verify(signature_id: str):
    return success(data=verify_signature(signature_id))
