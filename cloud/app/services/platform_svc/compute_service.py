"""隐私计算服务，管理安全计算任务、联邦学习轮次与贡献审计。"""

# FROZEN — 代码保留不迭代。参见 BioPulse-整体战略规划-v2.3-final.md 第2章

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from starlette import status

from cloud.app.repositories import (
    PrivacyComputeJobsRepository,
)
from cloud.app.services.platform_svc.compute_scheduler import ComputeSchedulerMixin
from shared.base_service import BaseService

SCHEME_MAP = {
    "low": "DP",
    "medium": "DP+FL",
    "high": "FL+HE",
    "critical": "DP+FL+HE",
}


def _job_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "compute_type": row["compute_type"],
        "sensitivity_level": row["sensitivity_level"],
        "data_summary": row["data_summary"],
        "selected_scheme": row["selected_scheme"],
        "status": row["status"],
        "epsilon_used": row["epsilon_used"],
        "noise_level": row["noise_level"],
        "result_summary": row["result_summary"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }


class ComputeService(ComputeSchedulerMixin, BaseService):
    """隐私计算服务，提供可信计算任务、联邦学习及贡献验证功能。"""

    def create_job(self, compute_type: str, sensitivity_level: str, data_summary: str, user_id: int) -> dict:
        repo = PrivacyComputeJobsRepository(self._connection())
        job_id = f"pc:{uuid4()}"
        scheme = SCHEME_MAP.get(sensitivity_level, "DP+FL")
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row_id = repo.create(
            {
                "job_id": job_id,
                "compute_type": compute_type,
                "sensitivity_level": sensitivity_level,
                "data_summary": data_summary,
                "selected_scheme": scheme,
                "status": "pending",
                "created_by": user_id,
                "created_at": now,
            }
        )
        row = repo.get_by_id(row_id)
        return _job_to_dict(row)

    def list_jobs(self, status_filter: Optional[str] = None, compute_type: Optional[str] = None) -> list:
        repo = PrivacyComputeJobsRepository(self._connection())
        conditions, params = [], []
        if status_filter:
            conditions.append("status=?")
            params.append(status_filter)
        if compute_type:
            conditions.append("compute_type=?")
            params.append(compute_type)
        rows = repo.list_all(
            conditions=conditions or None,
            params=params or None,
            order_by="created_at DESC",
        )
        return [_job_to_dict(r) for r in rows]

    def get_job(self, job_id: str) -> dict:
        repo = PrivacyComputeJobsRepository(self._connection())
        rows = repo.list_all(conditions=["job_id=?"], params=[job_id])
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compute job not found",
            )
        return _job_to_dict(rows[0])
