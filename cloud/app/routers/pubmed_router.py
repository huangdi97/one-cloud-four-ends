"""PubMed 路由：关键词搜索与作者搜索。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cloud.app.services.intel.pubmed_service import search_pubmed
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/pubmed", tags=["pubmed"])


class SearchRequest(BaseModel):
    """PubMed 搜索请求体。"""

    keyword: str
    max_results: int = 20


@router.post("/search", summary="关键词搜索", description="根据关键词搜索PubMed论文，返回标题、作者、期刊和日期", tags=["pubmed"])
def search(body: SearchRequest, _: dict = Depends(require_scope("research"))):
    """Search PubMed papers by keyword. Returns title, authors, journal, date."""
    papers = search_pubmed(body.keyword, body.max_results)
    return success(data=papers)


@router.post("/author/{author_name}", summary="作者搜索", description="根据作者姓名搜索PubMed论文", tags=["pubmed"])
def search_by_author(author_name: str, _: dict = Depends(require_scope("research"))):
    """Search PubMed papers by author name. Uses [AU] qualifier."""
    papers = search_pubmed(f"{author_name}[AU]", max_results=20)
    return success(data=papers)
