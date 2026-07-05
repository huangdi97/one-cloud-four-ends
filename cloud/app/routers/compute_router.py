# FROZEN — 代码保留不迭代。参见 BioPulse-整体战略规划-v2.3-final.md 第2章
"""隐私计算路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.platform_svc.compute_service import ComputeService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/compute", tags=["Privacy Computing"])


class ComputeJobCreate(BaseModel):
    compute_type: str
    sensitivity_level: str = "medium"
    data_summary: str = ""


class FederatedInit(BaseModel):
    model_name: str
    num_rounds: int = 5
    aggregation_method: str = "fed_avg"


class FederatedSubmit(BaseModel):
    round_id: str
    participant_id: str
    metrics: dict = {}
    update_summary: str = ""


class TrustFedProve(BaseModel):
    contribution_id: int


@router.post(
    "/job/create", status_code=status.HTTP_201_CREATED, summary="创建隐私计算任务", description="创建一个新的隐私计算任务", tags=["Privacy Computing"]
)
def job_create(
    body: ComputeJobCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: ComputeService = Depends(),
):
    """创建隐私计算任务。"""
    user_id = int(current_user["sub"])
    row = service.create_job(
        compute_type=body.compute_type,
        sensitivity_level=body.sensitivity_level,
        data_summary=body.data_summary,
        user_id=user_id,
    )
    return success(data=row)


@router.get("/job/list", summary="列出计算任务", description="按状态和计算类型等条件列出计算任务", tags=["Privacy Computing"])
def job_list(
    status: Optional[str] = Query(None),
    compute_type: Optional[str] = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: ComputeService = Depends(),
):
    """列出计算任务。"""
    rows = service.list_jobs(status_filter=status, compute_type=compute_type)
    return success(data=rows)


@router.get("/job/{job_id}", summary="获取计算任务详情", description="根据任务ID获取计算任务详细信息", tags=["Privacy Computing"])
def job_detail(
    job_id: str,
    current_user: dict = Depends(require_scope("visit")),
    service: ComputeService = Depends(),
):
    """获取计算任务详情。"""
    row = service.get_job(job_id)
    return success(data=row)


@router.post(
    "/federated/init",
    status_code=status.HTTP_201_CREATED,
    summary="初始化联邦学习",
    description="初始化一个新的联邦学习过程",
    tags=["Privacy Computing"],
)
def federated_init(
    body: FederatedInit,
    current_user: dict = Depends(require_scope("visit")),
    service: ComputeService = Depends(),
):
    """初始化联邦学习。"""
    rows = service.init_federated(
        model_name=body.model_name,
        num_rounds=body.num_rounds,
        aggregation_method=body.aggregation_method,
    )
    return success(data=rows)


@router.post(
    "/federated/submit",
    status_code=status.HTTP_201_CREATED,
    summary="提交联邦学习结果",
    description="提交联邦学习参与方的计算结果",
    tags=["Privacy Computing"],
)
def federated_submit(
    body: FederatedSubmit,
    current_user: dict = Depends(require_scope("visit")),
    service: ComputeService = Depends(),
):
    """提交联邦学习结果。"""
    row = service.submit_federated(
        round_id=body.round_id,
        participant_id=body.participant_id,
        metrics=body.metrics,
        update_summary=body.update_summary,
    )
    return success(data=row)


@router.get("/federated/rounds/list", summary="列出联邦学习轮次", description="按模型名称和状态列出联邦学习轮次", tags=["Privacy Computing"])
def rounds_list(
    model_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: ComputeService = Depends(),
):
    """列出联邦学习轮次。"""
    rows = service.list_federated_rounds(model_name=model_name, status_filter=status)
    return success(data=rows)


@router.post("/trustfed/prove", summary="生成可信联邦贡献证明", description="生成可信联邦学习的贡献证明", tags=["Privacy Computing"])
def trustfed_prove(
    body: TrustFedProve,
    current_user: dict = Depends(require_scope("visit")),
    service: ComputeService = Depends(),
):
    """生成可信联邦贡献证明。"""
    proof = service.prove_contribution(
        contribution_id=body.contribution_id,
        prover_sub=current_user.get("sub", "unknown"),
    )
    return success(data=proof)


@router.get("/trustfed/verify/{contribution_id}", summary="验证贡献证明", description="验证指定的联邦学习贡献证明", tags=["Privacy Computing"])
def trustfed_verify(
    contribution_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: ComputeService = Depends(),
):
    """验证贡献证明。"""
    result = service.verify_contribution(contribution_id)
    return success(data=result)
