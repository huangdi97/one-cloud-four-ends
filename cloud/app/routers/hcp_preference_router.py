"""HCP channel preference APIs."""

from fastapi import APIRouter

from cloud.app.services.rep_workbench.hcp_channel_preference import get_preferred_strategy
from shared.base import success

router = APIRouter(prefix="/api/hcp", tags=["HCP渠道偏好"])


@router.get("/{hcp_id}/preference", tags=["HCP渠道偏好"])
def hcp_preference(hcp_id: str):
    return success(data=get_preferred_strategy(hcp_id))
