"""模型压缩路由：量化/张量分解压缩类型查询、作业管理与策略对比。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cloud.app.services.platform_svc.model_compression_service import (
    BASE_PARAM_COUNTS,
    COMPRESSION_TYPES,
    ModelCompressionService,
)
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(
    prefix="/model-compression",
    tags=["模型压缩"],
    dependencies=[Depends(require_scope("research"))],
)


class CompressRequest(BaseModel):
    """模型压缩请求体。"""

    compression_type: str


@router.get("/types", summary="压缩类型列表", description="获取所有可用的模型压缩类型", tags=["Model Compression"])
def get_available_types(
    service: ModelCompressionService = Depends(),
) -> Any:
    return success(data=service.get_available_types())


@router.post("/compress", summary="压缩模型", description="对指定模型执行压缩操作", tags=["Model Compression"])
def compress_model(
    body: CompressRequest,
    service: ModelCompressionService = Depends(),
) -> Any:
    return success(data=service.compress(body.model_name, body.compression_type))


@router.get("/jobs", summary="任务列表", description="获取所有压缩任务列表，可按状态筛选", tags=["Model Compression"])
def list_jobs(
    status: Optional[str] = None,
    service: ModelCompressionService = Depends(),
) -> Any:
    return success(data=service.list_jobs(status))


@router.get("/jobs/{job_id}", summary="任务详情", description="获取指定压缩任务的详细信息", tags=["Model Compression"])
def get_job(
    job_id: str,
    service: ModelCompressionService = Depends(),
) -> Any:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="压缩任务不存在")
    return success(data=job)


@router.delete("/jobs/{job_id}", summary="删除任务", description="删除指定的压缩任务", tags=["Model Compression"])
def delete_job(
    job_id: str,
    service: ModelCompressionService = Depends(),
) -> Any:
    if not service.delete_job(job_id):
        raise HTTPException(status_code=404, detail="压缩任务不存在")
    return success(data={"deleted": True})


@router.get("/compare/{model_name}", summary="策略对比", description="对比指定模型的不同压缩策略效果", tags=["Model Compression"])
def compare_strategies(
    model_name: str,
) -> Any:
    params_before = BASE_PARAM_COUNTS.get(model_name, 50000000)
    original_size = int(params_before * 4)
    rows = []
    for key, ct in COMPRESSION_TYPES.items():
        compressed_size = int(original_size * (1 - ct["compression_ratio"]))
        params_after = int(params_before * (1 - ct["compression_ratio"] * 0.7))
        rows.append(
            {
                "type": key,
                "name": ct["name"],
                "compression_ratio": ct["compression_ratio"],
                "accuracy_impact": ct["accuracy_impact"],
                "original_size_bytes": original_size,
                "compressed_size_bytes": compressed_size,
                "params_before": params_before,
                "params_after": params_after,
            }
        )
    return success(data=rows)
