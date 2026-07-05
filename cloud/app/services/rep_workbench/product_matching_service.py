"""产品匹配服务，基于 Jaccard 相似度对 PI 研究方向与方法描述进行产品匹配。"""

from typing import Any

from cloud.app.services.rep_workbench.product_match_scorer import (
    _compute_jaccard_score,
    _parse_json_list,
    _tokenize,
)


def match_products_for_pi(pi_id: int, top_k: int = 3, research_db=None) -> list[dict[str, Any]]:
    """根据 PI 研究方向为其匹配最相关的产品。

    将 PI 的研究领域描述与产品关键词/名称进行 Jaccard 相似度计算，
    返回 top_k 个最匹配的产品。

    Args:
        pi_id: PI 的用户 ID
        top_k: 返回的最大匹配数量，默认 3
        research_db: 可选的研究数据库连接，为 None 时自动创建

    Returns:
        匹配结果列表，每项含 product_id、name、category、score、match_reason
    """
    from cloud.app.research_database import get_research_db

    close_db = False
    if research_db is None:
        research_db = get_research_db()
        close_db = True
    try:
        product_count = research_db.execute("SELECT COUNT(*) FROM research_products").fetchone()[0]
        if product_count == 0:
            return []
        row = research_db.execute("SELECT * FROM research_pi_profiles WHERE pi_id = ?", (pi_id,)).fetchone()
        if not row:
            return []
        pi = dict(row)
        research_areas = _parse_json_list(pi.get("research_areas", "[]"))
        area_tokens = set()
        for area in research_areas:
            area_tokens.update(_tokenize(area))
        if not area_tokens:
            return []
        product_rows = research_db.execute("SELECT * FROM research_products").fetchall()
        scored = []
        for p in product_rows:
            prod = dict(p)
            product_keywords = _parse_json_list(prod.get("keywords", "[]"))
            prod_name_tokens = _tokenize(prod.get("name", ""))
            all_prod_tokens = set(product_keywords) | prod_name_tokens
            score = _compute_jaccard_score(area_tokens, all_prod_tokens)
            if score > 0:
                scored.append(
                    {
                        "product_id": prod["product_id"],
                        "name": prod["name"],
                        "category": prod.get("category", ""),
                        "score": score,
                        "match_reason": f"Similarity: {score:.2f}",
                    }
                )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    finally:
        if close_db:
            research_db.close()


def match_products_by_method(method_description: str, top_k: int = 3, research_db=None) -> list[dict[str, Any]]:
    """根据方法描述匹配最相关的产品。

    将方法描述分词后与产品关键词/名称进行 Jaccard 相似度计算，
    返回 top_k 个最匹配的产品。

    Args:
        method_description: 方法描述文本
        top_k: 返回的最大匹配数量，默认 3
        research_db: 可选的研究数据库连接，为 None 时自动创建

    Returns:
        匹配结果列表，每项含 product_id、name、category、score、match_reason
    """
    if not method_description.strip():
        return []
    from cloud.app.research_database import get_research_db

    close_db = False
    if research_db is None:
        research_db = get_research_db()
        close_db = True
    try:
        method_tokens = _tokenize(method_description)
        if not method_tokens:
            return []
        product_rows = research_db.execute("SELECT * FROM research_products").fetchall()
        scored = []
        for p in product_rows:
            prod = dict(p)
            product_keywords = _parse_json_list(prod.get("keywords", "[]"))
            prod_name_tokens = _tokenize(prod.get("name", ""))
            all_prod_tokens = set(product_keywords) | prod_name_tokens
            score = _compute_jaccard_score(method_tokens, all_prod_tokens)
            if score > 0:
                scored.append(
                    {
                        "product_id": prod["product_id"],
                        "name": prod["name"],
                        "category": prod.get("category", ""),
                        "score": score,
                        "match_reason": f"Similarity: {score:.2f}",
                    }
                )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    finally:
        if close_db:
            research_db.close()
