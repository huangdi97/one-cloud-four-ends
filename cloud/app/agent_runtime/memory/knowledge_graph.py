"""合规知识图谱：实体抽取 → 图构建 → 模式发现 → 查询。"""

import logging
from collections import Counter
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ComplianceGraph:
    """使用 NetworkX 构建合规知识图谱，支持模式发现与社区检测。"""

    def __init__(self):
        self._graph = None
        self._entities: list[dict] = []
        self._relationships: list[dict] = []

    def extract_entities(self, texts: list[str]) -> list[dict]:
        """从文本列表中抽取合规相关实体。"""
        entities = []
        seen = set()
        for text in texts:
            lower = text.lower()
            rules = {
                "drug": ["aspirin", "metformin", "atorvastatin", "lisinopril", "omeprazole"],
                "regulation": ["fda", "ema", "nmpa", "hipaa", "gxp"],
                "action": ["prescribe", "audit", "approve", "review", "report"],
                "risk": ["adverse", "violation", "non-compliance", "fraud"],
                "hcp": ["dr.", "prof.", "specialist", "physician"],
            }
            for etype, keywords in rules.items():
                for kw in keywords:
                    if kw in lower:
                        dedup_key = (etype, kw)
                        if dedup_key not in seen:
                            seen.add(dedup_key)
                            entities.append(
                                {
                                    "type": etype,
                                    "name": kw,
                                    "source": text[:60],
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                            )
        self._entities = entities
        logger.info("ComplianceGraph: extracted %d entities", len(entities))
        return entities

    def build_graph(self) -> Any:
        """基于实体与关系构建 NetworkX 图。"""
        import networkx as nx

        g = nx.Graph()
        entity_map: dict[str, dict] = {}

        for ent in self._entities:
            node_id = f"{ent['type']}:{ent['name']}"
            entity_map[node_id] = ent
            g.add_node(node_id, **ent)

        types = [e["type"] for e in self._entities]
        type_pairs = list(zip(types[:-1], types[1:]))
        pair_counts = Counter(type_pairs)

        for (t1, t2), count in pair_counts.items():
            nodes_t1 = [n for n in g.nodes if n.startswith(f"{t1}:")]
            nodes_t2 = [n for n in g.nodes if n.startswith(f"{t2}:")]
            for n1 in nodes_t1:
                for n2 in nodes_t2:
                    if n1 != n2 and not g.has_edge(n1, n2):
                        g.add_edge(n1, n2, weight=count, relation=f"{t1}_to_{t2}")

        self._graph = g
        logger.info("ComplianceGraph: built graph with %d nodes, %d edges", g.number_of_nodes(), g.number_of_edges())
        return g

    def find_patterns(self, min_community_size: int = 2) -> list[dict]:
        """使用社区检测发现合规模式。"""
        if self._graph is None:
            logger.warning("ComplianceGraph: graph not built yet")
            return []

        import networkx as nx

        try:
            communities = list(nx.algorithms.community.greedy_modularity_communities(self._graph))
        except Exception:
            communities = []

        patterns = []
        for i, comm in enumerate(communities):
            if len(comm) < min_community_size:
                continue
            node_types = Counter()
            edges_inside = 0
            for node in comm:
                node_types[self._graph.nodes[node].get("type", "unknown")] += 1
            for u in comm:
                for v in comm:
                    if self._graph.has_edge(u, v):
                        edges_inside += 1
            patterns.append(
                {
                    "community_id": i,
                    "size": len(comm),
                    "node_types": dict(node_types.most_common()),
                    "internal_edges": edges_inside,
                    "members": sorted(comm),
                }
            )

        logger.info("ComplianceGraph: found %d patterns", len(patterns))
        return patterns

    def query(self, entity_type: str | None = None, relation: str | None = None) -> list[dict]:
        """查询图谱中的节点与边。"""
        if self._graph is None:
            return []

        results = []
        for node, data in self._graph.nodes(data=True):
            if entity_type and data.get("type") != entity_type:
                continue
            neighbors = list(self._graph.neighbors(node))
            edges = []
            for nb in neighbors:
                edge_data = self._graph.get_edge_data(node, nb)
                if relation and edge_data.get("relation") != relation:
                    continue
                edges.append(
                    {
                        "target": nb,
                        "relation": edge_data.get("relation"),
                        "weight": edge_data.get("weight", 1),
                    }
                )
            if edges or not relation:
                results.append(
                    {
                        "node": node,
                        "type": data.get("type"),
                        "name": data.get("name"),
                        "edges": edges,
                    }
                )

        return results

    def clear(self) -> None:
        """清空图谱和实体列表。"""
        self._graph = None
        self._entities = []
        self._relationships = []
