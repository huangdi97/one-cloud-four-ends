"""联邦节点聚合服务，提供联邦学习节点的数据汇总与分析。"""

from typing import Optional

from cloud.app.repositories import FederatedNodesRepository, FederatedRoundsRepository
from cloud.app.repositories.audit_repository import AuditLogsRepository, FedAuditContributionsRepository
from cloud.app.services.platform_svc.fed_weight_calculator import (
    audit_log_to_dict,
    contribution_to_dict,
    is_node_compliant,
    since_datetime,
    to_csv,
)
from shared.base_service import BaseService


class FedAggregator(BaseService):
    def get_dashboard(self, days: Optional[int] = None) -> dict:
        """汇总联邦节点、轮次、审计与合规看板数据。

        Args:
            days: 可选的最近天数窗口，用于过滤审计日志。

        Returns:
            包含节点统计、轮次、审计日志、贡献记录和合规计数的字典。

        Raises:
            HTTPException: 当底层仓储查询失败时由调用栈抛出。
        """
        node_repo = FederatedNodesRepository(self._connection())
        round_repo = FederatedRoundsRepository(self._connection())
        audit_repo = AuditLogsRepository(self._connection())
        contrib_repo = FedAuditContributionsRepository(self._connection())
        all_nodes = node_repo.get_all()
        total = len(all_nodes)
        online = sum(1 for n in all_nodes if n["status"] == "online")
        total_samples = sum(n["total_samples"] or 0 for n in all_nodes)
        total_rounds = sum(n["round_count"] or 0 for n in all_nodes)
        status_dist = {}
        type_dist = {}
        for n in all_nodes:
            s = n["status"]
            status_dist[s] = status_dist.get(s, 0) + 1
            t = n["node_type"]
            type_dist[t] = type_dist.get(t, 0) + 1
        since = since_datetime(days) if days else None
        if since:
            audit_cond = ["created_at>=?"]
            audit_params = [since]
        else:
            audit_cond = None
            audit_params = None
        recent_audit_logs = audit_repo.list_all(conditions=audit_cond, params=audit_params, order_by="created_at DESC")
        recent_audit_logs = [audit_log_to_dict(r) for r in recent_audit_logs[:20]]
        contribs = contrib_repo.get_recent(limit=10)
        contribs = [contribution_to_dict(c) for c in contribs]
        compliance_count = sum(1 for n in all_nodes if is_node_compliant(n["status"], n.get("reliability_score")))
        data_usage_count = sum(1 for c in contribs if c.get("verified") is True)
        recent_rounds = round_repo.list_all(order_by="created_at DESC", params=[])
        recent_rounds = [dict(r) for r in recent_rounds[:5]]
        return {
            "total_nodes": total,
            "online_nodes": online,
            "total_rounds": total_rounds,
            "total_samples": total_samples,
            "status_distribution": status_dist,
            "type_distribution": type_dist,
            "recent_rounds": recent_rounds,
            "audit_logs": recent_audit_logs,
            "audit_contributions": contribs,
            "compliant_nodes": compliance_count,
            "verified_data_usage": data_usage_count,
        }

    def export_dashboard_csv(self, days: Optional[int] = None) -> str:
        """导出联邦看板审计摘要CSV。

        Args:
            days: 可选的最近天数窗口，用于过滤看板审计日志。

        Returns:
            CSV文本，字段包含id、动作、实体、详情和创建时间。

        Raises:
            HTTPException: 当看板数据读取失败时由调用栈抛出。
        """
        data = self.get_dashboard(days=days)
        rows = []
        for log in data["audit_logs"]:
            rows.append(
                {
                    "id": log["id"],
                    "action": log["action"],
                    "entity_type": log["entity_type"],
                    "entity_id": log["entity_id"],
                    "detail": log.get("detail", ""),
                    "created_at": log["created_at"],
                }
            )
        if not rows:
            rows = [{"id": "", "action": "", "entity_type": "", "entity_id": "", "detail": "", "created_at": ""}]
        return to_csv(rows, ["id", "action", "entity_type", "entity_id", "detail", "created_at"])

    def get_audit_log(self, days: Optional[int] = None) -> dict:
        """读取联邦操作日志和合规贡献记录。

        Args:
            days: 可选的最近天数窗口，用于过滤操作日志。

        Returns:
            包含operation_logs和compliance_checks的字典。

        Raises:
            HTTPException: 当底层日志查询失败时由调用栈抛出。
        """
        audit_repo = AuditLogsRepository(self._connection())
        contrib_repo = FedAuditContributionsRepository(self._connection())
        since = since_datetime(days) if days else None
        if since:
            audit_cond = ["created_at>=?"]
            audit_params = [since]
        else:
            audit_cond = None
            audit_params = None
        logs = audit_repo.list_all(conditions=audit_cond, params=audit_params, order_by="created_at DESC")
        logs = [audit_log_to_dict(r) for r in logs]
        contribs = contrib_repo.list_all(order_by="created_at DESC")
        contribs = [contribution_to_dict(c) for c in contribs]
        return {"operation_logs": logs, "compliance_checks": contribs}

    def get_compliance_summary(self) -> list:
        """生成所有联邦节点的合规摘要。

        Args:
            None.

        Returns:
            每个节点的状态、可靠性、样本数和合规结果列表。

        Raises:
            HTTPException: 当节点查询失败时由调用栈抛出。
        """
        repo = FederatedNodesRepository(self._connection())
        all_nodes = repo.get_all()
        result = []
        for n in all_nodes:
            result.append(
                {
                    "node_id": n["node_id"],
                    "node_name": n["node_name"],
                    "status": n["status"],
                    "reliability_score": n["reliability_score"],
                    "is_active": n["is_active"],
                    "total_samples": n["total_samples"],
                    "last_heartbeat": n["last_heartbeat"],
                    "compliant": is_node_compliant(n["status"], n.get("reliability_score")),
                }
            )
        return result

    def export_audit_log_csv(self, days: Optional[int] = None) -> str:
        """导出联邦审计日志和合规检查CSV。

        Args:
            days: 可选的最近天数窗口，用于过滤操作日志。

        Returns:
            CSV文本，合并操作日志与合规贡献记录。

        Raises:
            HTTPException: 当审计数据读取失败时由调用栈抛出。
        """
        data = self.get_audit_log(days=days)
        rows = []
        for log in data["operation_logs"]:
            rows.append(
                {
                    "type": "operation",
                    "id": log["id"],
                    "user_id": log.get("user_id", ""),
                    "action": log["action"],
                    "entity_type": log["entity_type"],
                    "entity_id": log["entity_id"],
                    "detail": log.get("detail", ""),
                    "created_at": log["created_at"],
                }
            )
        for c in data["compliance_checks"]:
            rows.append(
                {
                    "type": "compliance",
                    "id": c["id"],
                    "user_id": c.get("contributor_did", ""),
                    "action": c.get("contribution_type", ""),
                    "entity_type": "fed_contribution",
                    "entity_id": c.get("payload_hash", ""),
                    "detail": c.get("payload_summary", ""),
                    "created_at": c["created_at"],
                }
            )
        if not rows:
            rows = [
                {
                    "type": "",
                    "id": "",
                    "user_id": "",
                    "action": "",
                    "entity_type": "",
                    "entity_id": "",
                    "detail": "",
                    "created_at": "",
                }
            ]
        return to_csv(rows, ["type", "id", "user_id", "action", "entity_type", "entity_id", "detail", "created_at"])
