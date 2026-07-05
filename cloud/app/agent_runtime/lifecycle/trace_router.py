"""Trace 查询路由 — 查看单条 trace、按条件搜索、指标汇总。"""
# ruff: noqa: E501

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, StreamingResponse

from cloud.app.agent_runtime.comm.streamer import AgentStreamer
from cloud.app.agent_runtime.core.agent_registry import AgentRegistry
from cloud.app.agent_runtime.lifecycle.trace_html import TraceHTMLRenderer
from cloud.app.agent_runtime.lifecycle.trace_service import TraceService
from cloud.app.agent_runtime.tools.metrics import get_metrics
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/agent", tags=["Agent Traces"])

_streamer: AgentStreamer | None = None


def get_streamer() -> AgentStreamer:
    """get streamer."""
    global _streamer
    if _streamer is None:
        _streamer = AgentStreamer()
    return _streamer


_trace_service: TraceService | None = None


def get_trace_service() -> TraceService:
    """Return the singleton TraceService instance."""
    global _trace_service
    if _trace_service is None:
        _trace_service = TraceService()
    return _trace_service


@router.get("/traces/ui", tags=["Agent Traces"], include_in_schema=False)
def trace_dashboard_ui(user=Depends(require_scope("visit"))):
    """Agent Trace Dashboard HTML UI."""
    from fastapi.responses import HTMLResponse

    return HTMLResponse(TraceHTMLRenderer.render_dashboard())


@router.get("/traces/ui/agents", tags=["Agent Traces"], include_in_schema=False)
def agent_status_ui(user=Depends(require_scope("visit"))):
    """Agent 状态概览 HTML 页面 — 列出所有注册 Agent 的名称/角色/状态/最后活跃时间。"""
    from fastapi.responses import HTMLResponse

    agents = AgentRegistry.list()
    tracer = get_trace_service().get_tracer()

    rows_html = ""
    for agent in agents:
        _ = agent.identity.key  # noqa: F841
        name = agent.identity.name
        role = agent.identity.role
        status = "online"
        last_active = "-"
        last_result = "-"
        success_rate = "-"

        traces = tracer.list_traces(agent_name=name, page=1, page_size=5)
        items = traces.get("items", [])
        if items:
            last_active = items[0].get("started_at", items[0].get("created_at", "-"))
            last_result = items[0].get("status", "-")

        all_traces = tracer.list_traces(agent_name=name, page=1, page_size=1000)
        all_items = all_traces.get("items", [])
        if all_items:
            success_count = sum(1 for t in all_items if t.get("status") == "success")
            success_rate = f"{round(success_count / len(all_items) * 100, 1)}%"

        rows_html += f"""<tr>
<td>{name}</td>
<td>{role}</td>
<td><span class="badge {"success" if status == "online" else "warning"}">{status}</span></td>
<td>{last_active}</td>
<td><span class="badge {"success" if last_result == "success" else ("error" if last_result == "error" else "warning")}">{last_result}</span></td>
<td>{success_rate}</td>
</tr>"""

    return HTMLResponse(TraceHTMLRenderer.render_agents_page(rows_html))


@router.get(
    "/traces/{trace_id}",
    tags=["Agent Traces"],
    operation_id="agents_get_trace",
    summary="获取单条trace详情",
    response_description="返回trace详情",
)
def get_trace(trace_id: str, user=Depends(require_scope("visit"))):
    """Retrieve a single trace by ID."""
    svc = get_trace_service()
    trace = svc.get_trace(trace_id)
    if trace is None:
        from fastapi import HTTPException
        from starlette import status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return success(data=trace)


@router.get("/traces", tags=["Agent Traces"], operation_id="agents_list_traces", summary="列出Agent执行记录", response_description="返回trace列表")
def list_traces(
    agent_name: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(require_scope("visit")),
):
    svc = get_trace_service()
    result = svc.list_traces(agent_name=agent_name, page=page, page_size=page_size)
    return success(data=result)


@router.get("/metrics", tags=["Agent Traces"], response_class=PlainTextResponse)
def prometheus_metrics():
    return PlainTextResponse(get_metrics())


@router.get(
    "/metrics/summary",
    tags=["Agent Traces"],
    operation_id="agents_metrics_summary",
    summary="获取指标汇总",
    response_description="返回指标汇总",
)
def metrics_summary(user=Depends(require_scope("visit"))):
    svc = get_trace_service()
    return success(data=svc.get_metrics_summary())


@router.get(
    "/eval/dashboard",
    tags=["Agent Traces"],
    operation_id="agents_eval_dashboard",
    summary="获取Agent评估面板",
    response_description="返回评估数据",
)
def eval_dashboard(user=Depends(require_scope("visit"))):
    svc = get_trace_service()
    return success(data=svc.get_eval_dashboard())


@router.get("/traces/{trace_id}/stream", tags=["Agent Traces"])
def stream_trace(trace_id: str, user=Depends(require_scope("visit"))):
    streamer = get_streamer()
    return StreamingResponse(
        streamer.get_stream(trace_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/config/secrets", tags=["Agent Traces"], operation_id="config_list_secrets", summary="列出所有密钥状态", include_in_schema=False)
def list_secrets(user=Depends(require_scope("admin"))):
    svc = get_trace_service()
    return success(data=svc.list_secrets())


@router.post("/config/secrets/{key_name}", tags=["Agent Traces"], operation_id="config_set_secret", summary="设置密钥值", include_in_schema=False)
def set_secret(key_name: str, body: dict, user=Depends(require_scope("admin"))):
    from fastapi import HTTPException
    from starlette import status as http_status

    value = body.get("value", "")
    if not value:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="value is required")
    svc = get_trace_service()
    return success(data=svc.set_secret(key_name, value))


@router.delete("/config/secrets/{key_name}", tags=["Agent Traces"], operation_id="config_delete_secret", summary="删除密钥", include_in_schema=False)
def delete_secret(key_name: str, user=Depends(require_scope("admin"))):
    svc = get_trace_service()
    return success(data=svc.delete_secret(key_name))


@router.get(
    "/checkpoints/recoverable",
    tags=["Agent Traces"],
    operation_id="checkpoints_list_recoverable",
    summary="列出可恢复的checkpoint",
    include_in_schema=False,
)  # noqa: E501
def list_recoverable(user=Depends(require_scope("admin"))):
    svc = get_trace_service()
    return success(data=svc.list_recoverable())


@router.post(
    "/checkpoints/{trace_id}/resume",
    tags=["Agent Traces"],
    operation_id="checkpoints_resume",
    summary="恢复执行中断的checkpoint",
    include_in_schema=False,
)  # noqa: E501
def resume_checkpoint(trace_id: str, body: dict, user=Depends(require_scope("admin"))):
    svc = get_trace_service()
    result = svc.resume_checkpoint(trace_id, body.get("auth_header", ""))
    if result is None:
        from fastapi import HTTPException
        from starlette import status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checkpoint not found")
    return success(data=result)


@router.get("/slo/alerts", tags=["Agent Traces"], operation_id="slo_list_alerts", summary="获取SLO告警记录", include_in_schema=False)
def slo_alerts(
    agent_name: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_scope("visit")),
):
    from cloud.app.agent_runtime.lifecycle.slo_monitor import get_breach_summary

    summary = get_breach_summary(hours=24)
    if agent_name:
        summary["breaches"] = [b for b in summary["breaches"] if b.get("agent_name") == agent_name]
        summary["total_breaches"] = len(summary["breaches"])
    return success(data=summary)


def log_agent_decision(
    agent_name: str,
    input_summary: str,
    decisions: list,
    risk_level: str,
    approval_status: str,
    human_reviewer: str = "",
) -> None:
    svc = get_trace_service()
    svc.log_agent_decision(agent_name, input_summary, decisions, risk_level, approval_status, human_reviewer)


def get_agent_decisions(
    agent_name: str | None = None,
    risk_level: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> list[dict]:
    svc = get_trace_service()
    return svc.get_agent_decisions(agent_name, risk_level, date_from, date_to, limit)


def auto_audit_decision(
    agent_name: str,
    input_summary: str,
    decisions: list,
    risk_level: str,
) -> None:
    svc = get_trace_service()
    svc.auto_audit_decision(agent_name, input_summary, decisions, risk_level)
