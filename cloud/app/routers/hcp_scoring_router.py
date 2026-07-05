"""HCP influence scoring APIs."""

from fastapi import APIRouter

from cloud.app.services.rep_workbench.hcp_scoring_service import calculate_score
from shared.base import success

router = APIRouter(prefix="/api/hcp", tags=["HCP评分"])


@router.get("/{id}/score", tags=["HCP评分"])
def get_hcp_score(id: str):
    return success(data=calculate_score(id))
