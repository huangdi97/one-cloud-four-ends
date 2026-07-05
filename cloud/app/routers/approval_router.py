from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette import status

from cloud.app.services.platform_svc.approval_service import ApprovalService
from shared.auth_scope import require_scope
from shared.base import success


class QuotationSubmit(BaseModel):
    """报价审批提交请求。"""

    quotation_id: str = Field(..., description="报价单ID")
    amount: float = Field(..., description="报价金额")
    customer_id: str = Field(..., description="客户ID")
    notes: Optional[str] = Field(None, description="备注")


class ReviewRequest(BaseModel):
    """审批请求。"""

    action: str = Field(..., pattern="^(approve|reject)$", description="审批动作")
    notes: Optional[str] = Field(None, description="审批意见")


router = APIRouter(prefix="/api/v1/quotation", tags=["报价审批"])


@router.post("/approve", status_code=status.HTTP_201_CREATED, summary="提交报价审批", tags=["报价审批"])
def submit_quotation(body: QuotationSubmit, _: dict = Depends(require_scope("visit")), service: ApprovalService = Depends()):
    result = service.submit_quotation(body.model_dump())
    return success(data=result)


@router.get("/pending", summary="获取待审批列表", tags=["报价审批"])
def get_pending(service: ApprovalService = Depends()):
    result = service.get_pending()
    return success(data=result)


@router.post("/{quotation_id}/review", summary="经理审批通过/驳回", tags=["报价审批"])
def review(quotation_id: str, body: ReviewRequest, _: dict = Depends(require_scope("visit")), service: ApprovalService = Depends()):
    result = service.review(quotation_id, body.action, body.notes)
    if not result:
        raise HTTPException(404, "quotation not found")
    return success(data=result)
