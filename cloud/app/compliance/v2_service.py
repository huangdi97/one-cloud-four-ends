"""Compliance V2 facade over the evaluator and report generator."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, Request

from cloud.app.database import get_db
from cloud.app.services.compliance_svc.rule_evaluator import RuleEvaluator
from cloud.app.services.rep_workbench.report_generator import ReportGenerator
from shared.base_service import BaseService


class ComplianceV2Service(BaseService):
    """Compliance V2 facade over the evaluator and report generator."""

    def __init__(self, db: Any = Depends(get_db)):
        """初始化 ComplianceV2Service，创建评估器和报告生成器。"""
        super().__init__(db)
        self._evaluator = RuleEvaluator(self.db)
        self._reporter = ReportGenerator(self.db)

    def scan(self, body: Any, request: Request, uid: int) -> dict[str, Any]:
        """执行合规扫描，返回检测结果。"""
        return self._evaluator.scan(body, request, uid)

    def list_records(
        self,
        message_type: Optional[str],
        risk_level: Optional[str],
        passed: Optional[int],
        date_from: Optional[str],
        date_to: Optional[str],
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """分页查询合规检测记录，支持按类型/风险等级/结果筛选。"""
        return self._evaluator.list_records(message_type, risk_level, passed, date_from, date_to, page, page_size)

    def get_record(self, record_id: int) -> dict[str, Any]:
        """根据 ID 获取单条合规检测记录详情。"""
        return self._evaluator.get_record(record_id)

    def review_record(self, record_id: int, body: Any, uid: int) -> dict[str, Any]:
        """人工审核合规记录，更新审核结果。"""
        return self._reporter.review_record(record_id, body, uid)

    def create_audit_chain(self, body: Any, uid: int) -> dict[str, Any]:
        """创建合规审计链记录。"""
        return self._reporter.create_audit_chain(body, uid)

    def get_audit_chain(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        """查询指定实体的审计链。"""
        return self._reporter.get_audit_chain(entity_type, entity_id)

    def verify_audit_chain(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        """验证指定实体的审计链完整性。"""
        return self._reporter.verify_audit_chain(entity_type, entity_id)

    def train_correction(self, record_id: int, request: Request, uid: int) -> dict[str, Any]:
        """提交人工纠偏结果用于模型训练。"""
        return self._reporter.train_correction(record_id, request, uid)

    def list_corrections(
        self,
        category: Optional[str],
        severity: Optional[str],
        status: Optional[str],
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """分页查询纠偏记录，支持按分类/严重度/状态筛选。"""
        return self._reporter.list_corrections(category, severity, status, page, page_size)

    def update_correction(self, correction_id: int, body: Any) -> dict[str, Any]:
        """更新指定纠偏记录的内容。"""
        return self._reporter.update_correction(correction_id, body)

    def list_l2_rules(self) -> dict[str, Any]:
        """返回所有 L2 合规规则列表。"""
        return self._evaluator.list_l2_rules()

    def evaluate_visit(self, body: Any) -> dict[str, Any]:
        """对单次拜访数据进行合规评估。"""
        return self._evaluator.evaluate_visit(body)

    def dashboard(self) -> dict[str, Any]:
        """返回合规检测总览仪表盘数据。"""
        return self._reporter.dashboard()


ComplianceV = ComplianceV2Service
