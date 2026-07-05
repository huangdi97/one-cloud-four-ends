"""MRC content workflow state machine — orchestration layer."""

import warnings

from cloud.app.services.intel.mrc_workflow_crud import (
    approve,
    create_material,
    distribute,
    get_workflow_detail,
    mrc_decision,
    submit_compliance,
    submit_mrc,
    track,
)

__all__ = ["approve", "create_material", "distribute", "get_workflow_detail", "mrc_decision", "submit_compliance", "submit_mrc", "track"]

warnings.warn(
    "cloud.app.services.mrc_workflow_service is deprecated",
    DeprecationWarning,
    stacklevel=2,
)
