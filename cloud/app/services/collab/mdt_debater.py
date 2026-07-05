"""MDT辩论服务，负责多学科团队辩论会话的管理与AI辩论编排。"""

import logging

from fastapi import HTTPException
from starlette import status

from cloud.app.repositories import (
    AgentRolesRepository,
    MdtOpinionsRepository,
    MdtParticipantsRepository,
    MdtSessionsRepository,
)
from cloud.app.services.collab.mdt_debate_scorer import _call_ai, parse_ai_opinion, parse_consensus_json
from shared.base import success
from shared.base_service import BaseService
from shared.datetime_utils import now as _now

logger = logging.getLogger(__name__)


class MdtDebater(BaseService):
    """MDT 辩论服务，管理多学科团队辩论会话与 AI 辩论编排。"""

    def create_session(self, body, uid: int) -> dict:
        """创建一个MDT辩论会话并写入参与者。

        Args:
            body: 包含标题、问题、上下文和参与者定义的请求体。
            uid: 创建会话的用户ID。

        Returns:
            标准成功响应，包含新会话ID、标题和参与者数量。

        Raises:
            HTTPException: 当底层仓储写入失败时由调用栈抛出。
        """
        n = _now()
        sessions_repo = MdtSessionsRepository(self._connection())
        participants_repo = MdtParticipantsRepository(self._connection())
        roles_repo = AgentRolesRepository(self._connection())
        sid = sessions_repo.create(
            {
                "title": body.title,
                "question": body.question,
                "context": body.context,
                "status": "active",
                "created_by": uid,
                "created_at": n,
                "updated_at": n,
            }
        )
        parts = body.participants
        if not parts:
            from cloud.app.mdt_engine_router import ParticipantDef

            roles = roles_repo.list_active(limit=5)
            parts = [ParticipantDef(agent_role_id=r["id"], role_name=r["name"], stance="neutral", vote_weight=1.0) for r in roles]
        for p in parts:
            participants_repo.create_raw(
                {
                    "session_id": sid,
                    "agent_role_id": p.agent_role_id,
                    "role_name": p.role_name,
                    "stance": p.stance,
                    "vote_weight": p.vote_weight,
                    "created_at": n,
                }
            )
        return success({"id": sid, "title": body.title, "participant_count": len(parts)})

    def list_sessions(self, status_filter, page: int, page_size: int) -> dict:
        """分页列出MDT辩论会话。

        Args:
            status_filter: 可选的会话状态过滤条件。
            page: 当前页码。
            page_size: 每页数量。

        Returns:
            标准成功响应，包含会话列表和分页信息。

        Raises:
            HTTPException: 当数据库分页查询失败时由调用栈抛出。
        """
        sessions_repo = MdtSessionsRepository(self._connection())
        conditions, params = [], []
        if status_filter:
            conditions.append("status=?")
            params.append(status_filter)
        total, total_pages, items = sessions_repo.paginate(
            page=page,
            page_size=page_size,
            conditions=conditions or None,
            params=params or None,
            order_by="created_at DESC",
        )
        return success({"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages})

    def get_session(self, session_id: int) -> dict:
        """读取单个MDT会话及其参与者和观点。

        Args:
            session_id: MDT会话ID。

        Returns:
            标准成功响应，包含会话、参与者和观点列表。

        Raises:
            HTTPException: 当会话不存在时抛出404。
        """
        sessions_repo = MdtSessionsRepository(self._connection())
        participants_repo = MdtParticipantsRepository(self._connection())
        opinions_repo = MdtOpinionsRepository(self._connection())
        s = sessions_repo.get_by_id(session_id)
        if not s:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MDT Session not found")
        parts = participants_repo.list_by_session(session_id)
        opinions = opinions_repo.list_by_session(session_id)
        return success({"session": s, "participants": parts, "opinions": opinions})

    def debate(self, session_id: int, max_rounds: int, auth_header: str) -> dict:
        """运行指定轮数的MDT AI辩论。

        Args:
            session_id: MDT会话ID。
            max_rounds: 本次需要推进的最大辩论轮数。
            auth_header: 透传给AI网关的认证头。

        Returns:
            标准成功响应，包含最新轮次和各参与者生成结果。

        Raises:
            HTTPException: 当会话不存在、已完成或没有参与者时抛出。
        """
        sessions_repo = MdtSessionsRepository(self._connection())
        participants_repo = MdtParticipantsRepository(self._connection())
        opinions_repo = MdtOpinionsRepository(self._connection())
        roles_repo = AgentRolesRepository(self._connection())
        s = sessions_repo.get_by_id(session_id)
        if not s:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MDT Session not found")
        if s["status"] == "completed":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Session already completed")
        participants = participants_repo.list_by_session(session_id)
        if not participants:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No participants in session")
        current_round = s["round_count"] or 0
        results = []
        for _ in range(max_rounds):
            current_round += 1
            prev = opinions_repo.build_round_summary(session_id, current_round - 1)
            for p in participants:
                role = roles_repo.get_system_prompt(p["agent_role_id"])
                if not role:
                    continue
                json_fmt = '\n\n请以JSON格式输出你的观点：{"opinion":"你的详细观点","summary":"一句话总结","sentiment":"positive/negative/neutral/constructive/mixed/analytical","confidence":0.0-1.0,"key_points":["要点1","要点2"]}'
                sys_msg = role["system_prompt"] + json_fmt
                user_msg = f"问题：{s['question']}\n背景：{s['context']}"
                if prev:
                    user_msg += f"\n\n上一轮各方观点摘要：\n{prev}"
                try:
                    ai = _call_ai([{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], auth_header)
                    reply = ai.get("reply", "")
                    parsed = parse_ai_opinion(reply)
                    opinions_repo.create_raw(
                        {
                            "session_id": session_id,
                            "participant_id": p["id"],
                            "round_number": current_round,
                            "opinion": parsed["opinion"],
                            "summary": parsed["summary"],
                            "sentiment": parsed["sentiment"],
                            "confidence": parsed["confidence"],
                            "key_points": parsed["key_points"],
                            "ai_response_raw": reply,
                            "tokens_used": ai.get("usage", {}).get("total_tokens", 0),
                            "created_at": _now(),
                        }
                    )
                    results.append(
                        {
                            "participant_id": p["id"],
                            "round": current_round,
                            "sentiment": parsed["sentiment"],
                            "confidence": parsed["confidence"],
                        }
                    )
                except Exception:  # noqa: BLE001  # AI call / JSON parse / DB ops can fail
                    logger.exception("Debate AI call failed for participant %s round %d", p["id"], current_round)
                    results.append({"participant_id": p["id"], "round": current_round, "error": "AI call failed"})
        sessions_repo.update_fields(session_id, {"round_count": current_round, "updated_at": _now()})
        return success({"round": current_round, "results": results})

    def get_opinions(self, session_id: int, round_number: int | None = None) -> dict:
        """查询MDT会话的观点列表。

        Args:
            session_id: MDT会话ID。
            round_number: 可选的辩论轮次过滤条件。

        Returns:
            标准成功响应，包含观点及参与者信息。

        Raises:
            HTTPException: 当会话不存在时抛出404。
        """
        sessions_repo = MdtSessionsRepository(self._connection())
        opinions_repo = MdtOpinionsRepository(self._connection())
        s = sessions_repo.get_by_id(session_id)
        if not s:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MDT Session not found")
        rows = opinions_repo.list_by_session_with_participant(session_id)
        if round_number is not None:
            rows = [r for r in rows if r.get("round_number") == round_number]
        return success(rows)

    def timeline(self, session_id: int) -> dict:
        """构建MDT会话按轮次组织的时间线。

        Args:
            session_id: MDT会话ID。

        Returns:
            标准成功响应，包含会话、轮次观点和完成后的共识信息。

        Raises:
            HTTPException: 当会话不存在时抛出404。
        """
        sessions_repo = MdtSessionsRepository(self._connection())
        opinions_repo = MdtOpinionsRepository(self._connection())
        s = sessions_repo.get_by_id(session_id)
        if not s:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MDT Session not found")
        opinions = opinions_repo.list_by_session_with_participant(session_id)
        rounds: dict = {}
        for o in opinions:
            rn = str(o["round_number"])
            rounds.setdefault(rn, []).append(o)
        timeline_data = {
            "session": s,
            "rounds": [{"round_number": int(k), "opinions": v} for k, v in sorted(rounds.items(), key=lambda x: int(x[0]))],
        }
        if s["status"] == "completed" and s.get("consensus"):
            timeline_data["consensus"] = {
                "text": s["consensus"],
                "detail": parse_consensus_json(s.get("consensus_json")),
                "updated_at": s["updated_at"],
            }
        return success(timeline_data)
