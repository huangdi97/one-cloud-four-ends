"""采集点击 / 停留 / 反馈信号，推断用户当前状态（意图 / 情绪 / 疲劳度）。"""

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = "data/user_state.json"


@dataclass
class SignalSample:
    """单次用户信号采样。"""

    event_type: str  # click / dwell / feedback / scroll / keypress
    value: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class InferredState:
    """推断出的用户状态。"""

    intent: str = "unknown"  # 当前意图标签
    emotion: str = "neutral"  # 情绪标签
    fatigue: float = 0.0  # 疲劳度 0~1
    engagement: float = 0.5  # 参与度 0~1
    confidence: float = 0.0  # 推断置信度
    updated_at: str = ""


class UserStatePerceiver:
    """采集点击 / 停留 / 反馈信号，实时推断用户意图、情绪、疲劳度。

    使用滑动窗口维护近期信号，通过加权规则推断用户状态。
    """

    def __init__(self, storage_path: str = DEFAULT_STATE_PATH, window_size: int = 50):
        """Initialize perceiver with a sliding signal window and persistence."""
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._window: dict[str, deque[SignalSample]] = {
            "click": deque(maxlen=window_size),
            "dwell": deque(maxlen=window_size),
            "feedback": deque(maxlen=window_size),
            "scroll": deque(maxlen=window_size),
            "keypress": deque(maxlen=window_size),
        }
        self._current_state = InferredState()
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    data = json.load(f)
                self._current_state = InferredState(**data.get("state", {}))
            except Exception as e:
                logger.warning("UserStatePerceiver: failed to load %s: %s", self._path, e)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(
                {
                    "state": {
                        "intent": self._current_state.intent,
                        "emotion": self._current_state.emotion,
                        "fatigue": self._current_state.fatigue,
                        "engagement": self._current_state.engagement,
                        "confidence": self._current_state.confidence,
                        "updated_at": self._current_state.updated_at,
                    }
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        tmp.replace(self._path)

    def record_signal(self, event_type: str, value: float, metadata: dict | None = None) -> InferredState:
        """记录一个用户信号并触发状态推断。

        Args:
            event_type: 信号类型 (click/dwell/feedback/scroll/keypress)
            value: 信号数值（如停留秒数、评分 1-5、滚动像素）
            metadata: 附加上下文

        Returns:
            更新后的推断状态
        """
        sample = SignalSample(event_type=event_type, value=value, metadata=metadata or {})
        with self._lock:
            if event_type in self._window:
                self._window[event_type].append(sample)
            self._current_state = self._infer()
            self._save()
        return self._current_state

    def _infer(self) -> InferredState:
        intent = self._infer_intent()
        emotion = self._infer_emotion()
        fatigue = self._compute_fatigue()
        engagement = self._compute_engagement()
        confidence = min(1.0, sum(len(q) / q.maxlen for q in self._window.values()) / len(self._window))
        return InferredState(
            intent=intent,
            emotion=emotion,
            fatigue=fatigue,
            engagement=engagement,
            confidence=confidence,
            updated_at=datetime.utcnow().isoformat(),
        )

    def _infer_intent(self) -> str:
        feedbacks = [s for s in self._window["feedback"] if s.value > 0]
        if feedbacks:
            recent = feedbacks[-1]
            if recent.value >= 4:
                return "satisfied"
            if recent.value <= 2:
                return "frustrated"
        clicks = list(self._window["click"])
        if len(clicks) > 10 and (clicks[-1].timestamp - clicks[0].timestamp) < 30:
            return "browsing_rapid"
        dwells = list(self._window["dwell"])
        if dwells and dwells[-1].value > 30:
            return "reading_deep"
        return "unknown"

    def _infer_emotion(self) -> str:
        feedbacks = list(self._window["feedback"])
        if feedbacks:
            avg = sum(s.value for s in feedbacks) / len(feedbacks)
            if avg >= 4:
                return "positive"
            if avg <= 2:
                return "negative"
        rapid_clicks = len(self._window["click"]) > 15
        high_scroll = list(self._window["scroll"]) and sum(s.value for s in self._window["scroll"]) > 5000
        if rapid_clicks and high_scroll:
            return "anxious"
        return "neutral"

    def _compute_fatigue(self) -> float:
        dwells = list(self._window["dwell"])
        if len(dwells) < 3:
            return 0.0
        session_duration = dwells[-1].timestamp - dwells[0].timestamp
        if session_duration < 60:
            return 0.0
        inactivity = time.time() - dwells[-1].timestamp
        fatigue = min(1.0, (session_duration / 3600) * 0.5 + (inactivity / 300) * 0.5)
        return round(fatigue, 4)

    def _compute_engagement(self) -> float:
        total_signals = sum(len(q) for q in self._window.values())
        if total_signals == 0:
            return 0.5
        recent = sum(1 for q in self._window.values() for s in q if time.time() - s.timestamp < 60)
        engagement = min(1.0, recent / max(1, total_signals) * 1.5)
        return round(engagement, 4)

    def get_current_state(self) -> InferredState:
        """获取当前推断的用户状态。"""
        with self._lock:
            return self._current_state

    def get_signals(self, event_type: str | None = None) -> list[SignalSample]:
        """获取指定类型的信号窗口数据。"""
        with self._lock:
            if event_type:
                return list(self._window.get(event_type, []))
            result = []
            for q in self._window.values():
                result.extend(q)
            return result

    def reset(self):
        """清空信号窗口，重置状态。"""
        with self._lock:
            for q in self._window.values():
                q.clear()
            self._current_state = InferredState()
            self._save()
