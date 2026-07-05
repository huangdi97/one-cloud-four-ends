"""Agent autonomous mixin — L4 autonomous cycle methods."""

import logging

from cloud.app.agent_runtime.core.models import Insight
from cloud.app.agent_runtime.core.shared_state import SharedStateEntry, get_shared_state

logger = logging.getLogger(__name__)


class AgentAutonomous:
    async def _compliance_autonomous_cycle(self, page_id: str, user_id: str) -> list[Insight]:
        """L4 自主行动循环: discover → collect_evidence → classify → notify.

        保持旧接口 _compliance_insights 供向后兼容。
        """
        try:
            from cloud.app.agent_runtime.comm.notifier import Notifier
            from cloud.app.services.compliance_svc.decision_intel_service import DecisionIntelService

            svc = DecisionIntelService()
            dashboard = svc.dashboard()
            total = dashboard.get("total_cases", 0)
            red_flags = dashboard.get("red_flag_count", 0) if isinstance(dashboard, dict) else 0

            # discover: 获取 red_light 案件
            red_light_cases = []
            if hasattr(svc, "list_red_light_cases"):
                red_light_cases = svc.list_red_light_cases() or []
            elif isinstance(dashboard, dict):
                red_light_cases = dashboard.get("red_light_cases", [])

            insights = []
            if total > 0:
                base_evidence = [
                    "来源: DecisionIntelService.dashboard",
                    f"数据: total_cases={total}, red_flags={red_flags}",
                    f"计算: red_flag_rate={red_flags / max(total, 1):.1%}",
                ]
                ss = get_shared_state()
                classified = {"low": [], "medium": [], "high": [], "critical": []}
                notifications = []

                for case in red_light_cases[:20]:
                    case_id = case.get("case_id", "") if isinstance(case, dict) else str(case)
                    case_desc = case.get("description", "") if isinstance(case, dict) else str(case)
                    severity_str = case.get("severity", "medium") if isinstance(case, dict) else "medium"

                    # collect_evidence: 关联查询拜访记录、费用、HCP
                    evidence_items = [f"案件: {case_id}"]
                    try:
                        from cloud.app.services.rep_workbench.visit_service import VisitService

                        vs = VisitService()
                        if hasattr(vs, "query_by_case"):
                            visit_data = vs.query_by_case(case_id)
                            evidence_items.append(f"关联拜访: {visit_data}")
                    except Exception:
                        evidence_items.append("关联拜访: 查询失败")

                    # classify: 按严重程度
                    severity = "critical" if severity_str == "critical" else severity_str
                    if severity not in classified:
                        severity = "medium"
                    classified[severity].append(case_id)

                    # collect_evidence → SharedState 写入
                    case_confidence = {"critical": 0.95, "high": 0.85, "medium": 0.7, "low": 0.5}.get(severity, 0.7)
                    ss.write(
                        SharedStateEntry(
                            namespace="compliance.result",
                            key=f"red_light_{case_id}",
                            value={"case_id": case_id, "description": case_desc, "severity": severity},
                            confidence=case_confidence,
                            agent_key=self.identity.key,
                            evidence=evidence_items,
                        ),
                        caller_agent_key=self.identity.key,
                    )

                    # notify: critical 走审批队列，其余 in-app 通知
                    notifier = Notifier()
                    if severity == "critical":
                        request_id = notifier.send_approval_request(
                            self.identity.key,
                            f"合规红灯-critial: {case_id}",
                            {"case_id": case_id, "severity": severity, "description": case_desc},
                        )
                        notifications.append(f"审批请求已发送: {request_id}")
                    else:
                        notifier.send(
                            f"[{severity.upper()}] 合规红灯: {case_id} - {case_desc[:100]}",
                            priority="high" if severity in ("high", "critical") else "normal",
                        )
                        notifications.append(f"通知已发送: {case_id}")

                summary = f"合规监控: {total} 个案件, {red_flags} 个红灯"
                if classified["critical"]:
                    summary += f", {len(classified['critical'])} 个紧急(已发起审批)"
                if classified["high"]:
                    summary += f", {len(classified['high'])} 个高危(已通知)"

                insights.append(
                    Insight(
                        agent_key=self.identity.key,
                        page_id=page_id,
                        summary=summary,
                        details={
                            "total_cases": total,
                            "red_flags": red_flags,
                            "classified": {k: len(v) for k, v in classified.items()},
                            "notifications": notifications[:5],
                        },
                        confidence=0.9,
                    )
                )
                ss.write(
                    SharedStateEntry(
                        namespace="compliance.result",
                        key=f"autonomous_cycle_{page_id}_{user_id}",
                        value={
                            "summary": summary,
                            "classified": {k: len(v) for k, v in classified.items()},
                            "notifications_sent": len(notifications),
                        },
                        confidence=0.9,
                        agent_key=self.identity.key,
                        evidence=base_evidence + [f"通知: {len(notifications)} 条已推送"],
                    ),
                    caller_agent_key=self.identity.key,
                )
            return insights
        except Exception:
            logger.exception("_compliance_autonomous_cycle failed")
            return []

    async def _opportunity_autonomous_cycle(self, page_id: str, user_id: str) -> list[Insight]:
        """L4 自主行动循环: detect_stalled → fetch_competitor_intel → generate_suggestion → notify.

        保持旧接口 _opportunity_insights 供向后兼容。
        """
        try:
            from datetime import datetime

            from cloud.app.agent_runtime.comm.notifier import Notifier
            from cloud.app.services.rep_workbench.opportunity_service import OpportunityService

            svc = OpportunityService()
            pipeline = svc.get_pipeline()
            total_value = pipeline.get("total_value", 0) if isinstance(pipeline, dict) else 0
            stage_count = pipeline.get("stage_count", 0) if isinstance(pipeline, dict) else 0
            opportunities = pipeline.get("opportunities", []) if isinstance(pipeline, dict) else []

            ss = get_shared_state()
            notifier = Notifier()
            insights = []
            stalled_count = 0
            suggestions = []

            for opp in opportunities[:20]:
                opp_id = opp.get("id", "") if isinstance(opp, dict) else ""
                opp_name = opp.get("name", "") if isinstance(opp, dict) else str(opp)
                stage = opp.get("stage", "") if isinstance(opp, dict) else ""
                last_activity_str = opp.get("last_activity_date", "") if isinstance(opp, dict) else ""
                owner = opp.get("owner", "") if isinstance(opp, dict) else ""
                value = opp.get("value", 0) if isinstance(opp, dict) else 0

                evidence_items = [
                    "来源: OpportunityService.get_pipeline",
                    f"商机: {opp_id} - {opp_name}",
                    f"阶段: {stage}",
                ]

                # detect_stalled: 检测超过 N 天无进展的商机
                stalled = False
                days_stalled = 0
                if last_activity_str:
                    try:
                        last_activity = datetime.fromisoformat(last_activity_str)
                        days_stalled = (datetime.now() - last_activity).days
                        if days_stalled > 30:
                            stalled = True
                            stalled_count += 1
                            evidence_items.append(f"停滞检测: {days_stalled} 天无进展")
                    except (ValueError, TypeError):
                        pass

                if not stalled:
                    continue

                # fetch_competitor_intel: 查询竞品情报
                competitor_info = "未获取"
                try:
                    from cloud.app.services.rep_workbench.visit_service import VisitService

                    vs = VisitService()
                    if hasattr(vs, "query_competitor_intel"):
                        competitor_info = vs.query_competitor_intel(opp_name) or "无竞品数据"
                        evidence_items.append(f"竞品情报: {str(competitor_info)[:100]}")
                except Exception:
                    evidence_items.append("竞品情报: 查询失败")

                # generate_suggestion: 生成推进建议
                if days_stalled > 60:
                    suggestion = "降价/转介绍：此商机已停滞超过60天，建议调整策略"
                elif days_stalled > 45:
                    suggestion = "增加拜访：此商机停滞超过45天，建议增加拜访频率"
                elif days_stalled > 30:
                    suggestion = "跟进提醒：此商机停滞超过30天，建议主动跟进"
                else:
                    suggestion = "常规跟进"

                suggestions.append(
                    {
                        "opp_id": opp_id,
                        "opp_name": opp_name,
                        "days_stalled": days_stalled,
                        "suggestion": suggestion,
                        "owner": owner,
                        "value": value,
                    }
                )
                evidence_items.append(f"建议: {suggestion}")

                # 写入 SharedState
                confidence = 0.7 if days_stalled <= 45 else (0.85 if days_stalled <= 60 else 0.95)
                ss.write(
                    SharedStateEntry(
                        namespace="opportunity.result",
                        key=f"stalled_{opp_id}",
                        value={
                            "opp_id": opp_id,
                            "opp_name": opp_name,
                            "days_stalled": days_stalled,
                            "stage": stage,
                            "owner": owner,
                            "value": value,
                            "competitor_intel": str(competitor_info)[:200],
                            "suggestion": suggestion,
                        },
                        confidence=confidence,
                        agent_key=self.identity.key,
                        evidence=evidence_items,
                    ),
                    caller_agent_key=self.identity.key,
                )

                # notify: 推送给相关销售代表
                if owner:
                    notifier.send(
                        f"[商机停滞] {opp_name} 已停滞 {days_stalled} 天 (负责人:{owner}) 建议: {suggestion}",
                        priority="high" if days_stalled > 60 else "normal",
                    )
                else:
                    notifier.send(
                        f"[商机停滞] {opp_name} 已停滞 {days_stalled} 天 建议: {suggestion}",
                        priority="high" if days_stalled > 60 else "normal",
                    )

            summary = f"管线总额 ¥{total_value:,.0f}，{stage_count} 个商机"
            if stalled_count:
                summary += f"，检测到 {stalled_count} 个停滞商机"

            if stalled_count > 0 or (stage_count and stage_count > 0):
                insights.append(
                    Insight(
                        agent_key=self.identity.key,
                        page_id=page_id,
                        summary=summary,
                        details={
                            "total_value": total_value,
                            "stage_count": stage_count,
                            "stalled_count": stalled_count,
                            "suggestions": suggestions[:5],
                        },
                        confidence=0.9,
                    )
                )
                ss.write(
                    SharedStateEntry(
                        namespace="opportunity.result",
                        key=f"autonomous_cycle_{page_id}_{user_id}",
                        value={
                            "summary": summary,
                            "stalled_count": stalled_count,
                            "suggestions_generated": len(suggestions),
                        },
                        confidence=0.9,
                        agent_key=self.identity.key,
                        evidence=["来源: OpportunityService", f"商机总数: {stage_count}", f"停滞: {stalled_count}", f"建议: {len(suggestions)} 条"],
                    ),
                    caller_agent_key=self.identity.key,
                )
            return insights
        except Exception:
            logger.exception("_opportunity_autonomous_cycle failed")
            return []
