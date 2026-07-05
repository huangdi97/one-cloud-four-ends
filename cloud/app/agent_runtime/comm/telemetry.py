"""轻量级 trace 系统 — 基于 logging + contextvars，无外部依赖。"""

import logging
import time
import uuid
from contextvars import ContextVar
from types import TracebackType

logger = logging.getLogger(__name__)

_trace_id: ContextVar[str | None] = ContextVar("_trace_id", default=None)
_parent_span_id: ContextVar[str | None] = ContextVar("_parent_span_id", default=None)


class TraceContext:
    """管理 trace_id + parent_span_id (contextvars)。"""

    @staticmethod
    def get_trace_id() -> str | None:
        """获取当前上下文的 trace_id。"""
        return _trace_id.get()

    @staticmethod
    def set_trace_id(tid: str | None) -> None:
        """设置当前上下文的 trace_id。"""
        _trace_id.set(tid)

    @staticmethod
    def get_parent_span_id() -> str | None:
        """获取当前上下文的 parent_span_id。"""
        return _parent_span_id.get()

    @staticmethod
    def set_parent_span_id(sid: str | None) -> None:
        """设置当前上下文的 parent_span_id。"""
        _parent_span_id.set(sid)

    @staticmethod
    def new_trace_id() -> str:
        """生成新的 trace_id。"""
        return uuid.uuid4().hex[:16]

    @staticmethod
    def new_span_id() -> str:
        """生成新的 span_id。"""
        return uuid.uuid4().hex[:16]

    @staticmethod
    def reset() -> None:
        """重置当前上下文的 trace_id 和 parent_span_id。"""
        _trace_id.set(None)
        _parent_span_id.set(None)


class trace_step:
    """Context manager 自动记录步骤开始/结束/耗时。

    Usage:
        with trace_step("llm_call", {"model": "gpt-4"}):
            ...
    """

    def __init__(self, name: str, attrs: dict | None = None) -> None:
        self._name = name
        self._attrs = attrs or {}
        self._span_id = TraceContext.new_span_id()
        self._start: float = 0.0
        self._parent_span_id: str | None = None
        self._trace_id: str | None = None

    def __enter__(self) -> "trace_step":
        self._trace_id = TraceContext.get_trace_id()
        if self._trace_id is None:
            self._trace_id = TraceContext.new_trace_id()
            TraceContext.set_trace_id(self._trace_id)

        self._parent_span_id = TraceContext.get_parent_span_id()
        TraceContext.set_parent_span_id(self._span_id)

        self._start = time.monotonic()
        logger.info(
            "TRACE step_start  trace=%s span=%s parent=%s name=%s attrs=%s",
            self._trace_id,
            self._span_id,
            self._parent_span_id or "",
            self._name,
            self._attrs,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        duration = int((time.monotonic() - self._start) * 1000)
        TraceContext.set_parent_span_id(self._parent_span_id)
        status = "error" if exc_type else "ok"
        logger.info(
            "TRACE step_end    trace=%s span=%s name=%s duration_ms=%d status=%s",
            self._trace_id,
            self._span_id,
            self._name,
            duration,
            status,
        )


def record_token_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost: float,
) -> None:
    """记录一次 LLM 调用的 token 消耗结构化日志。"""
    logger.info(
        "TRACE token_usage trace=%s model=%s prompt_tokens=%d completion_tokens=%d total_tokens=%d cost=%.6f",
        TraceContext.get_trace_id() or "",
        model,
        prompt_tokens,
        completion_tokens,
        prompt_tokens + completion_tokens,
        cost,
    )
