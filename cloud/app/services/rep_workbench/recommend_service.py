"""推荐服务，负责用户画像管理、行为记录与个性化推荐生成。"""

import json
import math
from typing import Optional

from fastapi import HTTPException
from starlette import status

from cloud.app.repositories import (
    KgEntitiesRepository,
    RecommendationsRepository,
    UserBehaviorsRepository,
    UserProfilesRepository,
)
from cloud.app.services.rep_workbench.recommend_filter import calc_dashboard_stats, paginate_behaviors
from shared.base import PaginatedResponse, validate_columns
from shared.base_service import BaseService
from shared.columns import TABLE_USER_PROFILES_COLS


class RecommendStrategyMixin:
    """个性化推荐生成和推荐列表策略。"""

    def generate_recommendations(self, user_id: int, rec_types: list, limit: int) -> list:
        behaviors_repo = UserBehaviorsRepository(self._connection())
        recs_repo = RecommendationsRepository(self._connection())
        kg_repo = KgEntitiesRepository(self._connection())
        behavior_count = behaviors_repo.count_by_user(user_id)
        results = []
        if behavior_count >= 3:
            top = behaviors_repo.top_action_by_user(user_id)
            if top:
                hot = behaviors_repo.top_targets_by_user_action(user_id, top["action_type"], limit)
                for i, t in enumerate(hot):
                    rt = rec_types[i % len(rec_types)]
                    rec_id = recs_repo.create(
                        {
                            "user_id": user_id,
                            "rec_type": rt,
                            "rec_target_id": t["target_id"],
                            "rec_title": t["target_id"],
                            "rec_reason": f"用户行为: {top['action_type']} 热度推荐",
                            "score": min(0.95, 0.5 + (i + 1) * 0.08),
                            "strategy_name": "hot-action",
                        }
                    )
                    results.append(recs_repo.get_by_id(rec_id))
        else:
            entities = kg_repo.top_active(limit)
            for i, e in enumerate(entities):
                rt = rec_types[i % len(rec_types)]
                rec_id = recs_repo.create(
                    {
                        "user_id": user_id,
                        "rec_type": rt,
                        "rec_target_id": e["entity_id"],
                        "rec_title": e["name"],
                        "rec_reason": f"知识图谱热门实体推荐: {e['entity_type']}",
                        "score": e["confidence"],
                        "strategy_name": "kg-popular",
                    }
                )
                results.append(recs_repo.get_by_id(rec_id))
        return results

    def list_recommendations(
        self,
        user_id: Optional[int] = None,
        rec_type: Optional[str] = None,
        clicked: Optional[int] = None,
        dismissed: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        recs_repo = RecommendationsRepository(self._connection())
        total, _, items = recs_repo.list_filtered(
            user_id=user_id,
            rec_type=rec_type,
            clicked=clicked,
            dismissed=dismissed,
            limit=limit,
            offset=offset,
        )
        page = offset // max(limit, 1) + 1
        total_pages = math.ceil(total / max(limit, 1))
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=limit,
            total_pages=total_pages,
        )


class RecommendService(RecommendStrategyMixin, BaseService):
    """推荐服务，提供用户画像管理、行为记录、个性化推荐生成与仪表盘统计。"""

    def create_profile(
        self,
        user_id: int,
        persona_type: str,
        specialization: str,
        experience_level: str,
        preferred_content_types: list,
        custom_tags: list,
    ) -> dict:
        """Create or upsert a user recommendation profile."""
        pct = json.dumps(preferred_content_types, ensure_ascii=False)
        tags = json.dumps(custom_tags, ensure_ascii=False)
        profiles_repo = UserProfilesRepository(self._connection())
        row = profiles_repo.upsert_profile(user_id, persona_type, specialization, experience_level, pct, tags)
        return row

    def get_profile(self, user_id: int) -> dict:
        """Retrieve a user's recommendation profile.

        Raises:
            HTTPException: 404 if the profile is not found.
        """
        profiles_repo = UserProfilesRepository(self._connection())
        row = profiles_repo.get_by_user_id(user_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
        return row

    def update_profile(
        self,
        user_id: int,
        persona_type: Optional[str] = None,
        specialization: Optional[str] = None,
        experience_level: Optional[str] = None,
        preferred_content_types: Optional[list] = None,
        custom_tags: Optional[list] = None,
    ) -> dict:
        """Update fields of an existing user recommendation profile.

        Raises:
            HTTPException: 404 if the profile is not found.
        """
        profiles_repo = UserProfilesRepository(self._connection())
        existing = profiles_repo.get_by_user_id(user_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
        updates = {}
        for field in ("persona_type", "specialization", "experience_level"):
            v = locals().get(field)
            if v is not None:
                updates[field] = v
        if preferred_content_types is not None:
            updates["preferred_content_types"] = json.dumps(preferred_content_types, ensure_ascii=False)
        if custom_tags is not None:
            updates["custom_tags"] = json.dumps(custom_tags, ensure_ascii=False)
        if not updates:
            return existing
        updates["updated_at"] = "NOW()"
        validate_columns(updates, "user_profiles", TABLE_USER_PROFILES_COLS)
        profiles_repo.update(
            profiles_repo.db.execute("SELECT id FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()["id"],
            {k: v for k, v in updates.items() if v != "NOW()"},
        )
        profiles_repo.db.execute("UPDATE user_profiles SET updated_at=NOW() WHERE user_id=?", (user_id,))
        profiles_repo.db.commit()
        row = profiles_repo.get_by_user_id(user_id)
        return row

    def log_behavior(
        self,
        user_id: int,
        action_type: str,
        target_type: str,
        target_id: str,
        metadata: dict,
        session_id: str,
        duration_seconds: int,
    ) -> dict:
        """Log a user behavior event for the recommendation engine."""
        behaviors_repo = UserBehaviorsRepository(self._connection())
        meta = json.dumps(metadata, ensure_ascii=False)
        row_id = behaviors_repo.create(
            {
                "user_id": user_id,
                "action_type": action_type,
                "target_type": target_type,
                "target_id": target_id,
                "metadata": meta,
                "session_id": session_id,
                "duration_seconds": duration_seconds,
            }
        )
        row = behaviors_repo.get_by_id(row_id)
        return row

    def behavior_history(
        self,
        user_id: Optional[int] = None,
        action_type: Optional[str] = None,
        target_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        """Retrieve paginated user behavior history with optional filters."""
        return paginate_behaviors(self.db, user_id, action_type, target_type, limit, offset)

    def mark_clicked(self, rec_id: int) -> None:
        """Mark a recommendation as clicked.

        Raises:
            HTTPException: 404 if the recommendation is not found.
        """
        recs_repo = RecommendationsRepository(self._connection())
        row = recs_repo.get_by_id(rec_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
        recs_repo.mark_clicked(rec_id)

    def mark_dismissed(self, rec_id: int) -> None:
        """Mark a recommendation as dismissed.

        Raises:
            HTTPException: 404 if the recommendation is not found.
        """
        recs_repo = RecommendationsRepository(self._connection())
        row = recs_repo.get_by_id(rec_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
        recs_repo.mark_dismissed(rec_id)

    def dashboard(self) -> dict:
        """Retrieve aggregated recommendation statistics for the dashboard."""
        return calc_dashboard_stats(self.db)
