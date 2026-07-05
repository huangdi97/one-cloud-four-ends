"""聚合多源信号（点击 / 停留 / 反馈 / 上下文），生成统一用户画像。"""

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from cloud.app.agent_runtime.perception.user_state import InferredState, UserStatePerceiver

logger = logging.getLogger(__name__)

DEFAULT_FUSION_PATH = "data/signal_fusion.json"


@dataclass
class UserProfile:
    """用户画像 — 多源信号融合后的结构化描述。"""

    user_id: str = ""
    top_intent: str = "unknown"
    emotion_trend: list[str] = field(default_factory=list)
    avg_engagement: float = 0.5
    avg_fatigue: float = 0.0
    session_count: int = 0
    preferred_features: list[str] = field(default_factory=list)
    pain_points: list[str] = field(default_factory=list)
    last_updated: str = ""


class SignalFusion:
    """聚合 UserStatePerceiver 的多源信号 + 外部上下文，生成用户画像。

    融合维度：
    - 用户状态信号（UserStatePerceiver）
    - 会话历史元数据
    - 时间衰减权重
    """

    def __init__(self, perceiver: UserStatePerceiver, storage_path: str = DEFAULT_FUSION_PATH):
        """Initialize signal fusion with a user state perceiver and storage path."""
        self._perceiver = perceiver
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._profiles: dict[str, UserProfile] = {}
        self._context_buffer: dict[str, list[dict]] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    data = json.load(f)
                for uid, pdata in data.items():
                    self._profiles[uid] = UserProfile(**pdata)
            except Exception as e:
                logger.warning("SignalFusion: failed to load %s: %s", self._path, e)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        serializable = {
            uid: {
                "user_id": p.user_id,
                "top_intent": p.top_intent,
                "emotion_trend": p.emotion_trend,
                "avg_engagement": p.avg_engagement,
                "avg_fatigue": p.avg_fatigue,
                "session_count": p.session_count,
                "preferred_features": p.preferred_features,
                "pain_points": p.pain_points,
                "last_updated": p.last_updated,
            }
            for uid, p in self._profiles.items()
        }
        with open(tmp, "w") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def ingest_context(self, user_id: str, context: dict):
        """注入外部上下文（如当前页面、任务、历史摘要）。

        Args:
            user_id: 用户标识
            context: 上下文 dict（如 page, task, session_id 等）
        """
        with self._lock:
            if user_id not in self._context_buffer:
                self._context_buffer[user_id] = []
            self._context_buffer[user_id].append(
                {
                    **context,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            if len(self._context_buffer[user_id]) > 100:
                self._context_buffer[user_id] = self._context_buffer[user_id][-100:]

    def fuse(self, user_id: str) -> UserProfile:
        """融合当前所有信号，生成或更新用户画像。

        Args:
            user_id: 用户标识

        Returns:
            融合后的用户画像
        """
        state = self._perceiver.get_current_state()
        with self._lock:
            profile = self._profiles.get(user_id, UserProfile(user_id=user_id))
            profile.top_intent = state.intent
            profile.emotion_trend.append(state.emotion)
            if len(profile.emotion_trend) > 20:
                profile.emotion_trend = profile.emotion_trend[-20:]

            alpha = 0.3
            profile.avg_engagement = round(alpha * state.engagement + (1 - alpha) * profile.avg_engagement, 4)
            profile.avg_fatigue = round(alpha * state.fatigue + (1 - alpha) * profile.avg_fatigue, 4)
            profile.session_count += 1
            profile.last_updated = datetime.utcnow().isoformat()
            profile = self._extract_preferences(profile, user_id)
            profile = self._detect_pain_points(profile, state)
            self._profiles[user_id] = profile
            self._save()
        return profile

    def _extract_preferences(self, profile: UserProfile, user_id: str) -> UserProfile:
        contexts = self._context_buffer.get(user_id, [])[-10:]
        feature_hits: dict[str, int] = {}
        for ctx in contexts:
            page = ctx.get("page", "") or ctx.get("feature", "")
            if page:
                feature_hits[page] = feature_hits.get(page, 0) + 1
        if feature_hits:
            threshold = max(2, max(feature_hits.values()) // 2)
            profile.preferred_features = [f for f, c in feature_hits.items() if c >= threshold]
        return profile

    def _detect_pain_points(self, profile: UserProfile, state: InferredState) -> UserProfile:
        if state.emotion == "negative" or state.emotion == "anxious":
            candidate = f"negative_emotion_{state.emotion}"
            if candidate not in profile.pain_points:
                profile.pain_points.append(candidate)
        if state.fatigue > 0.7:
            pain = "high_fatigue"
            if pain not in profile.pain_points:
                profile.pain_points.append(pain)
        if len(profile.pain_points) > 10:
            profile.pain_points = profile.pain_points[-10:]
        return profile

    def get_profile(self, user_id: str) -> UserProfile | None:
        """获取指定用户的画像。"""
        with self._lock:
            return self._profiles.get(user_id)

    def list_profiles(self) -> dict[str, UserProfile]:
        """返回所有用户画像。"""
        with self._lock:
            return dict(self._profiles)

    def reset_profile(self, user_id: str):
        """重置指定用户的画像。"""
        with self._lock:
            self._profiles.pop(user_id, None)
            self._context_buffer.pop(user_id, None)
            self._save()
