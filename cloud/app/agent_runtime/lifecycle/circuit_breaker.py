"""熔断器 — LLM API 连续失败时自动静默一段时间，防止无效重试。"""

import enum
import logging
import time

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker is open, retry after {retry_after:.0f}s")


class CircuitBreaker:
    """熔断器：连续 failure_threshold 次失败后开启熔断，
    recovery_timeout 秒后自动半开，允许一次试探请求。
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0.0

    def call(self, fn, *args, **kwargs):
        """Execute fn with circuit breaker protection, raising CircuitBreakerOpenError if open."""
        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            remaining = max(0.0, self.recovery_timeout - elapsed)
            if remaining > 0:
                raise CircuitBreakerOpenError(remaining)
            self.state = CircuitState.HALF_OPEN
            logger.info("Circuit breaker half-open, allowing trial request")
        try:
            result = fn(*args, **kwargs)
            if isinstance(result, dict) and not result.get("success", True):
                self.on_failure()
                return result
            self.on_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception as e:  # 调用可能抛出任意异常
            logger.warning("Circuit breaker熔断: %s", e, exc_info=True)
            self.on_failure()
            raise

    def on_success(self):
        """Reset circuit breaker to closed state after a successful call."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        logger.info("Circuit breaker closed after successful call")

    def on_failure(self):
        """Increment failure count and open circuit if threshold exceeded."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning("Circuit breaker failure %d/%d", self.failure_count, self.failure_threshold)
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error("Circuit breaker opened after %d failures", self.failure_count)

    def reset(self):
        """Manually reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
