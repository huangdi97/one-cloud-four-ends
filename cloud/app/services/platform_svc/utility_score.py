"""效用评分服务计算系统各项效用指标得分。"""

from datetime import datetime

from fastapi import HTTPException
from starlette import status

from cloud.app.repositories import (
    MemoryEntriesRepository,
    MemoryUtilityScoresRepository,
    NodeMemoryLinksRepository,
)
from cloud.app.services.platform_svc.utility_ranker import UtilityRankerMixin
from shared.datetime_utils import now as _now


class UtilityScoreMixin(UtilityRankerMixin):
    def _calc_utility(self, entry: dict, conn_count: int) -> dict:
        imp = entry["importance"] or 0.0
        ac = entry["access_count"] or 0
        la = entry["last_accessed"]
        access_freq = min(ac / 100.0, 1.0)
        if la is None:
            recency = 0.2
        else:
            try:
                days_ago = (datetime.now() - datetime.strptime(la, "%Y-%m-%d %H:%M:%S")).days
            except (ValueError, TypeError):
                days_ago = 999
            recency = 1.0 if days_ago <= 7 else (0.5 if days_ago <= 30 else 0.2)
        connectivity = min(conn_count / 5.0, 1.0)
        utility = round(0.3 * imp + 0.3 * access_freq + 0.2 * recency + 0.2 * connectivity, 4)
        return {
            "utility_score": utility,
            "access_frequency": access_freq,
            "recency_score": recency,
            "importance_score": imp,
            "connectivity_score": connectivity,
            "decay_rate": round(1.0 - utility, 4),
        }

    def score_memory(self, memory_id: int) -> dict:
        """对单条记忆条目计算并写入效用评分。"""
        entry_repo = MemoryEntriesRepository(self._connection())
        mus_repo = MemoryUtilityScoresRepository(self._connection())
        link_repo = NodeMemoryLinksRepository(self._connection())

        entry = entry_repo.find_active_by_id(memory_id)
        if not entry:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Memory entry not found")
        conn_count = link_repo.count_by_node(memory_id)
        u = self._calc_utility(entry, conn_count)
        now = _now()
        mus_repo.upsert_score(
            {
                "memory_entry_id": memory_id,
                "utility_score": u["utility_score"],
                "access_frequency": u["access_frequency"],
                "recency_score": u["recency_score"],
                "importance_score": u["importance_score"],
                "connectivity_score": u["connectivity_score"],
                "decay_rate": u["decay_rate"],
                "last_utility_update": now,
                "created_at": now,
            }
        )
        self.db.commit()
        return {"memory_id": memory_id, **u}

    def score_all(self) -> dict:
        """批量计算所有活跃记忆条目的效用评分。"""
        entry_repo = MemoryEntriesRepository(self._connection())
        mus_repo = MemoryUtilityScoresRepository(self._connection())
        link_repo = NodeMemoryLinksRepository(self._connection())

        rows = entry_repo.list_active_ordered(order_by="id")
        now = _now()
        processed = 0
        for r in rows:
            conn_count = link_repo.count_by_node(r["id"])
            u = self._calc_utility(r, conn_count)
            mus_repo.upsert_score(
                {
                    "memory_entry_id": r["id"],
                    "utility_score": u["utility_score"],
                    "access_frequency": u["access_frequency"],
                    "recency_score": u["recency_score"],
                    "importance_score": u["importance_score"],
                    "connectivity_score": u["connectivity_score"],
                    "decay_rate": u["decay_rate"],
                    "last_utility_update": now,
                    "created_at": now,
                }
            )
            processed += 1
        self.db.commit()
        return {"processed_count": processed}
