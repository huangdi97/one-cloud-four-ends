"""Medical representative license APIs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status

from cloud.app.schemas.rep_license import LicenseVerifyRequest
from cloud.app.services.platform_svc.rep_license_service import check_expiry, get_rep_license, verify_license
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/rep/license", tags=["医药代表备案"])


@router.post("/verify", tags=["医药代表备案"])
def rep_license_verify(body: LicenseVerifyRequest, _: dict = Depends(require_scope("visit"))):
    return success(data=verify_license(body.registration_no))


@router.get("/expiring", tags=["医药代表备案"])
def rep_license_expiring(days: int = Query(60, ge=1, le=365)):
    return success(data=check_expiry(days=days))


@router.get("/{rep_id}", tags=["医药代表备案"])
def rep_license_get(rep_id: str):
    license_ = get_rep_license(rep_id)
    if not license_:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Representative license not found")
    return success(data=license_)
