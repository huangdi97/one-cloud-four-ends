"""合规 V2 评估器，提供内容扫描、审计记录查询及 L2 规则列表。"""

import hashlib
import json
import urllib.request

from fastapi import Request

from cloud.app.compliance.strategy_service import ComplianceStrategyService
from cloud.app.repositories import (
    AuditChainEntriesRepository,
    ComplianceAuditRecordsRepository,
    ComplianceRulesRepository,
)
from cloud.app.services.compliance_svc.rule_aggregator import RuleAggregatorMixin, _parse_json
from shared.ai_gateway import LLM_INFERENCE_TIMEOUT
from shared.base import success
from shared.base_service import BaseService
from shared.compliance import check_content
from shared.config import settings as config_settings
from shared.datetime_utils import now as _now


def _call_ai(messages: list[dict], auth_header: str) -> dict:
    payload = {"messages": messages, "temperature": 0.7, "max_tokens": 2048}
    req = urllib.request.Request(
        f"{config_settings.ai_chat_url}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": auth_header},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=LLM_INFERENCE_TIMEOUT) as rp:
        return json.loads(rp.read().decode("utf-8")).get("data", {})


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class RuleEvaluator(RuleAggregatorMixin, BaseService):
    """规则评估器，支持文本/图片等多类型的合规扫描、风险评级与审计链归档。"""

    def __init__(self, db):
        super().__init__(db)
        self._strategy_service = ComplianceStrategyService(None)

    def scan(self, body, request: Request, uid: int) -> dict:
        n = _now()
        rules_repo = ComplianceRulesRepository(self._connection())
        audit_repo = ComplianceAuditRecordsRepository(self._connection())
        chain_repo = AuditChainEntriesRepository(self._connection())
        rules_rows = rules_repo.list_all()
        rules = [
            {
                "category": r["category"],
                "keyword": r["keyword"],
                "max_value": r["max_value"],
            }
            for r in rules_rows
        ]
        result = check_content(body.content, rules)
        violations = result.violations
        score = result.score
        ai_analysis = ""
        if body.message_type != "text":
            sys_prompt = '你是一名医药合规审查员。请分析以下内容是否存在合规风险，包括绝对化用语、疗效对比、不良反应缺失、剂量超标等问题。以JSON输出:{"passed":bool,"risk_level":"low/medium/high/critical","ai_violations":[string],"analysis_notes":""}'
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"[{body.message_type}]: {body.content}"},
            ]
            auth = request.headers.get("Authorization", "")
            ai_data = _call_ai(messages, auth)
            ai_reply = ai_data.get("reply", "")
            ai_parsed = _parse_json(ai_reply, {})
            if isinstance(ai_parsed, dict):
                ai_violations = ai_parsed.get("ai_violations", [])
                if isinstance(ai_violations, list):
                    violations = list(set(violations + ai_violations))
                if not ai_parsed.get("passed", True):
                    score = max(0.0, score - 0.3)
            ai_analysis = json.dumps(ai_parsed, ensure_ascii=False) if isinstance(ai_parsed, dict) else ai_reply
        risk_level = "low"
        if len(violations) >= 3 or score <= 0.3:
            risk_level = "critical"
        elif len(violations) >= 2 or score <= 0.5:
            risk_level = "high"
        elif len(violations) >= 1 or score <= 0.8:
            risk_level = "medium"
        passed = len(violations) == 0
        record_id = audit_repo.create(
            {
                "message_type": body.message_type,
                "content": body.content,
                "source_id": body.source_id,
                "score": score,
                "risk_level": risk_level,
                "passed": int(passed),
                "violations": json.dumps(violations, ensure_ascii=False),
                "ai_analysis": ai_analysis,
                "created_by": uid,
                "created_at": n,
            }
        )
        chain_repo.create(
            {
                "entity_type": "compliance_audit",
                "entity_id": str(record_id),
                "action": "scan",
                "previous_hash": "",
                "current_hash": hashlib.sha256(json.dumps({"action": "scan", "record_id": record_id}).encode()).hexdigest(),
                "payload": json.dumps(
                    {"record_id": record_id, "passed": passed, "risk_level": risk_level},
                    ensure_ascii=False,
                ),
                "source": body.source_id,
                "created_by": uid,
                "performed_at": n,
            }
        )
        return success(
            data={
                "record_id": record_id,
                "passed": passed,
                "score": score,
                "risk_level": risk_level,
                "violations": violations,
            }
        )

    def list_l2_rules(self) -> dict:
        return success(data={"rules": self._strategy_service.get_l2_rules()})

    def evaluate_visit(self, body) -> dict:
        strategy = ComplianceStrategyService(self.db)
        result = strategy.evaluate_visit(body.visit_data)
        return success(data=result)
