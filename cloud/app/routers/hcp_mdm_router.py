"""HCP master data management APIs."""

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from cloud.app.services.rep_workbench.hcp_mdm_service import dedup_check, get_hcp_profile, get_unified_profile, import_hcp_csv, merge_duplicates
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/mdm", tags=["HCP主数据"])


class MergeRequest(BaseModel):
    primary_id: str
    duplicate_ids: list[str] = Field(default_factory=list)


@router.get("/hcp/{id}", tags=["HCP主数据"])
def get_hcp(id: str, _: dict = Depends(require_scope(["pharma", "research"]))):
    return success(data=get_unified_profile(id))


@router.post("/dedup", tags=["HCP主数据"])
def dedup(_: dict = Depends(require_scope(["pharma", "research"]))):
    return success(data=dedup_check())


@router.post("/merge", tags=["HCP主数据"])
def merge(body: MergeRequest, _: dict = Depends(require_scope(["pharma", "research"]))):
    return success(data=merge_duplicates(body.primary_id, body.duplicate_ids))


@router.get("/duplicates", tags=["HCP主数据"])
def duplicates(_: dict = Depends(require_scope(["pharma", "research"]))):
    return success(data=dedup_check())


@router.post("/hcp/import", tags=["HCP主数据"])
def hcp_import(file: UploadFile = File(...), _: dict = Depends(require_scope(["pharma", "research"]))):
    csv_content = file.file.read().decode("utf-8-sig")
    return success(data=import_hcp_csv(csv_content))


@router.get("/hcp/{id}/profile", tags=["HCP主数据"])
def hcp_profile(id: str, _: dict = Depends(require_scope(["pharma", "research"]))):
    return success(data=get_hcp_profile(id))
