"""Agent analysis mixin — anomaly autonomous cycle methods."""

import logging

from cloud.app.agent_runtime.core.models import Insight
from cloud.app.agent_runtime.core.shared_state import SharedStateEntry, get_shared_state

logger = logging.getLogger(__name__)


class AgentAnalysis:
    async def _anomaly_autonomous_cycle(self, page_id: str, user_id: str) -> list[Insight]:
        """L4 自主行动循环: discover → generate_hypothesis → cross_verify → notify.

        保持旧接口 _anomaly_insights 供向后兼容。
        """
        try:
            from cloud.app.agent_runtime.analyzer.hypothesis import HypothesisEngine
            from cloud.app.agent_runtime.comm.notifier import Notifier
            from cloud.app.services.platform_svc.anomaly_context_service import AnomalyContextService

            svc = AnomalyContextService()
            if not hasattr(svc, "list_anomalies"):
                return []

            anomalies = svc.list_anomalies()
            count = len(anomalies) if isinstance(anomalies, list) else 0
            if count == 0:
                return []

            ss = get_shared_state()
            engine = HypothesisEngine()
            notifier = Notifier()
            insights = []
            hypothesis_entries = []

            for anomaly in anomalies[:10]:
                anomaly_id = anomaly.get("anomaly_id", "") if isinstance(anomaly, dict) else str(anomaly)
                anomaly_desc = anomaly.get("description", "") if isinstance(anomaly, dict) else str(anomaly)

                # discover: 获取异常模式
                anomaly_evidence = [
                    "来源: AnomalyContextService.list_anomalies",
                    f"数据: anomaly_id={anomaly_id}, description={anomaly_desc[:100]}",
                ]

                # generate_hypothesis: 调用 HypothesisEngine
                red_light_event = {"event_id": anomaly_id, "description": anomaly_desc}
                try:
                    hypothesis_result = engine.hypothesis_verification_loop(red_light_event)
                    hypotheses = hypothesis_result.get("hypotheses", [])
                    narrative = hypothesis_result.get("narrative", {})
                    hypothesis_entries.append(
                        {
                            "anomaly_id": anomaly_id,
                            "hypotheses": hypotheses,
                            "narrative": narrative.root_cause if hasattr(narrative, "root_cause") else "",
                        }
                    )
                    if hasattr(narrative, "reasoning_chain"):
                        anomaly_evidence.extend(narrative.reasoning_chain[:3])
                except Exception as e:
                    anomaly_evidence.append(f"假设生成失败: {str(e)[:100]}")

                # cross_verify: 跨 namespace 读取 compliance + visit + opportunity
                cross_evidence = []
                for ns in ["compliance.result", "visit.records", "opportunity.result"]:
                    ns_entries = ss.read(ns, min_confidence=0.3)
                    if ns_entries:
                        cross_evidence.append(f"交叉验证: {ns} 存在 {len(ns_entries)} 条相关记录")
                if cross_evidence:
                    anomaly_evidence.extend(cross_evidence[:3])

                # 计算置信度
                confidence = 0.8
                if hypothesis_entries and hypothesis_entries[-1].get("narrative"):
                    conf_val = getattr(narrative, "confidence", 0) if hasattr(narrative, "confidence") else 0
                    confidence = max(0.5, conf_val) if conf_val else 0.8
                if cross_evidence:
                    confidence = min(1.0, confidence + 0.1)

                # 写入 SharedState
                ss.write(
                    SharedStateEntry(
                        namespace="analysis.result",
                        key=f"anomaly_{anomaly_id}",
                        value={
                            "anomaly_id": anomaly_id,
                            "description": anomaly_desc,
                            "hypotheses": [h.get("description", "") for h in hypothesis_entries[-1].get("hypotheses", [])]
                            if hypothesis_entries
                            else [],
                            "root_cause": hypothesis_entries[-1].get("narrative", "") if hypothesis_entries else "",
                        },
                        confidence=confidence,
                        agent_key=self.identity.key,
                        evidence=anomaly_evidence,
                    ),
                    caller_agent_key=self.identity.key,
                )

                # 写入 hypothesis namespace
                if hypothesis_entries:
                    last_hyp = hypothesis_entries[-1]
                    for h in last_hyp.get("hypotheses", []):
                        ss.write(
                            SharedStateEntry(
                                namespace="analysis.hypothesis",
                                key=f"hyp_{h.get('id', 'unknown')}",
                                value=h,
                                confidence=h.get("confidence", 0.5),
                                agent_key=self.identity.key,
                                evidence=["来源: HypothesisEngine", f"假设: {h.get('description', '')}"],
                            ),
                            caller_agent_key=self.identity.key,
                        )

                # notify: 高置信度发现推送
                if confidence >= 0.7:
                    notifier.send(
                        f"[异常发现] {anomaly_desc[:100]} 置信度:{confidence:.0%}",
                        priority="high" if confidence >= 0.85 else "normal",
                    )

            summary = f"异常分析: {count} 个异常模式"
            if hypothesis_entries:
                confirmed = sum(1 for h in hypothesis_entries if h.get("narrative"))
                summary += f", {confirmed} 个已生成根因假设"

            insights.append(
                Insight(
                    agent_key=self.identity.key,
                    page_id=page_id,
                    summary=summary,
                    details={
                        "anomaly_count": count,
                        "hypothesis_count": len(hypothesis_entries),
                        "entries": hypothesis_entries[:5],
                    },
                    confidence=0.8,
                )
            )

            ss.write(
                SharedStateEntry(
                    namespace="analysis.result",
                    key=f"autonomous_cycle_{page_id}_{user_id}",
                    value={
                        "summary": summary,
                        "anomaly_count": count,
                        "hypothesis_count": len(hypothesis_entries),
                    },
                    confidence=0.8,
                    agent_key=self.identity.key,
                    evidence=["来源: AnomalyContextService + HypothesisEngine", f"异常数: {count}", f"假设数: {len(hypothesis_entries)}"],
                ),
                caller_agent_key=self.identity.key,
            )
            return insights
        except Exception:
            logger.exception("_anomaly_autonomous_cycle failed")
            return []
