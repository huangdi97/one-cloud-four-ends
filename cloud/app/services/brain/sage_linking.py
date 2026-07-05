"""智慧链接服务用于知识图谱中的实体链接与关联。"""

import json
import logging
from typing import Any

from cloud.app.repositories.sage_repository import SageRepository
from cloud.app.repositories.world_tree_repository import WorldTreeNodesRepository
from cloud.app.research_database import get_research_db
from cloud.app.services.brain.brain_memory_service import BrainMemoryService
from cloud.app.services.brain.world_tree_service import WorldTreeService

logger = logging.getLogger(__name__)


def _parse_area_string(val: str, ks: set) -> None:
    try:
        parsed = json.loads(val)
        if isinstance(parsed, dict):
            ks.update(parsed.keys())
        elif isinstance(parsed, list):
            ks.update(str(v) for v in parsed)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("sage_linking: failed to parse area field %s", e)


def _collect_episodic_by_session(ep_res: dict, ep_ids: set, by_session: dict) -> None:
    for it in ep_res.get("items", []):
        if it["id"] in ep_ids:
            sid = it.get("related_entity_id") or it.get("involved_agents", "")
            if sid:
                by_session.setdefault(sid, []).append(it["id"])


def _record_episodic_candidates(by_session: dict, result: dict) -> None:
    for sid, mids in by_session.items():
        if len(mids) > 1:
            result["episodic_to_semantic_candidates"] += 1
            result["details"]["episodic_to_semantic"].append(
                {"session_id": sid, "count": len(mids)},
            )


def _record_matched_areas(a: dict, b_item: dict, common: list, paired: set, result: dict, bms: BrainMemoryService) -> None:
    lower_common = {c.lower() for c in common}
    has_proc = any(p.get("title", "").lower() in lower_common for p in bms.procedural_recall("").get("items", []))
    if not has_proc:
        result["semantic_to_procedural_candidates"] += 1
        result["details"]["semantic_to_procedural"].append(
            {"memory_ids": [a["id"], b_item["id"]], "common_areas": common},
        )
        paired.update([a["id"], b_item["id"]])


def _execute_world_tree_link(wts, nodes, title, sem, result) -> None:
    wts.link_memory(nodes[title], sem["id"])
    result["world_tree_links_created"] += 1
    result["details"]["world_tree_links"].append(
        {"node_id": nodes[title], "memory_id": sem["id"]},
    )


def _handle_world_tree_link_error(result) -> None:
    logger.exception("链接异常3")
    result["pending_manual"] += 1


def _link_semantic_to_world_tree(sem, title, nodes, wts, result) -> None:
    try:
        _execute_world_tree_link(wts, nodes, title, sem, result)
    except Exception:  # noqa: BLE001  # 链接操作多步可能失败
        _handle_world_tree_link_error(result)


def _process_semantic_pairs(sem_items: list, paired: set, result: dict, bms: BrainMemoryService) -> None:
    for i, a in enumerate(sem_items):
        for b_item in sem_items[i + 1 :]:
            if a["id"] in paired or b_item["id"] in paired:
                continue
            common = _extract_common_area(a, b_item)
            if common:
                _record_matched_areas(a, b_item, common, paired, result, bms)


def _extract_common_area(a: dict, b: dict) -> list:
    keys_a, keys_b = set(), set()
    for field in ("area_weights", "active_areas"):
        for d, ks in ((a, keys_a), (b, keys_b)):
            val = d.get(field)
            if isinstance(val, dict):
                ks.update(val.keys())
            elif isinstance(val, str):
                _parse_area_string(val, ks)
            elif isinstance(val, (list, tuple)):
                ks.update(str(v) for v in val)
    return sorted(keys_a & keys_b)


class SageLinkingService:
    def __init__(self, db=None):
        self.db = db or get_research_db()
        self.repo = SageRepository(self._connection())

    def auto_link(self) -> dict:
        """自动执行情景→语义、语义→过程、世界树记忆链接三阶段关联。"""
        result: dict[str, Any] = {
            "episodic_to_semantic_candidates": 0,
            "semantic_to_procedural_candidates": 0,
            "world_tree_links_created": 0,
            "pending_manual": 0,
            "details": {
                "episodic_to_semantic": [],
                "semantic_to_procedural": [],
                "world_tree_links": [],
            },
        }
        bms = BrainMemoryService(db=self.db)

        try:
            scores: list[dict[str, Any]] = self.repo.get_all_scores()
            ep_ids = {s["memory_id"] for s in scores if s["memory_type"] == "episodic" and s["tier"] in ("hot", "warm")}
            if ep_ids:
                ep_res = bms.episodic_list(page=1, page_size=1000)
                by_session = {}
                _collect_episodic_by_session(ep_res, ep_ids, by_session)
                _record_episodic_candidates(by_session, result)
        except Exception:  # noqa: BLE001  # 链接操作多步可能失败
            logger.exception("链接异常")

        try:
            sem_items = bms.semantic_search("", limit=1000).get("items", [])
            paired = set()
            _process_semantic_pairs(sem_items, paired, result, bms)
        except Exception:  # noqa: BLE001  # 链接操作多步可能失败
            logger.exception("链接异常2")

        try:
            wt_repo = WorldTreeNodesRepository(self._connection())
            wts = WorldTreeService(db=self.db)
            nodes = {n["name"].lower(): n["id"] for n in wt_repo.list_active_sorted()}
            sem_for_link = bms.semantic_search("", limit=1000).get("items", [])
            for sem in sem_for_link:
                title = (sem.get("title") or "").lower()
                if title in nodes:
                    _link_semantic_to_world_tree(sem, title, nodes, wts, result)
        except Exception:  # noqa: BLE001  # 链接操作多步可能失败
            logger.exception("链接异常4")

        return result

    def get_status(self) -> dict:
        """返回各记忆组件计数、评分分布及最近一次评分/进化/链接时间。"""
        bms = BrainMemoryService(db=self.db)
        wt_repo = WorldTreeNodesRepository(self._connection())

        ep_res = bms.episodic_list(page=1, page_size=1)
        sem_res = bms.semantic_search("", limit=1)
        proc_res = bms.procedural_recall("")
        nodes = wt_repo.list_active_sorted()

        ep_total = ep_res.get("total", 0)
        sem_total = sem_res.get("total", 0) or len(sem_res.get("items", []))
        proc_total = len(proc_res.get("items", []))

        scores = self.repo.get_all_scores()
        tier_dist = {"hot": 0, "warm": 0, "cold": 0}
        for s in scores:
            tier_dist[s["tier"]] += 1

        logs = self.repo.get_recent_logs(limit=100)
        last_score = next((log["created_at"] for log in logs if log["action"] == "score"), "")
        last_evolve = next((log["created_at"] for log in logs if log["action"] == "evolve"), "")
        last_link = next((log["created_at"] for log in logs if log["action"] == "link"), "")

        return {
            "version": "0.1.0",
            "component_counts": {
                "episodic": ep_total,
                "semantic": sem_total,
                "procedural": proc_total,
                "world_tree_nodes": len(nodes),
            },
            "tier_distribution": tier_dist,
            "total_scored": len(scores),
            "last_scored_at": last_score,
            "last_evolved_at": last_evolve,
            "last_linked_at": last_link,
        }
