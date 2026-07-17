"""VectorMemory 单元测试 — 使用临时 SQLite 文件不依赖真实 embedding 模型。"""

from __future__ import annotations

import os
import tempfile

import pytest

from cloud.app.agent_runtime.memory.vector_memory import VectorMemory


@pytest.fixture
def vm():
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    mem = VectorMemory(db_path=tmp_path)
    mem._model = None
    yield mem
    os.unlink(tmp_path)


class TestVectorMemory:
    def test_store_and_search(self, vm: VectorMemory) -> None:
        vm.store(agent_name="test", key="k1", content="测试内容")
        results = vm.search(agent_name="test", query="测试")
        assert len(results) >= 1
        assert "测试内容" in results[0]["content"]

    def test_search_empty_db_returns_empty(self, vm: VectorMemory) -> None:
        results = vm.search(agent_name="test", query="任何内容")
        assert results == []

    def test_recall_exact_key(self, vm: VectorMemory) -> None:
        vm.store(agent_name="test", key="k1", content="测试内容")
        result = vm.recall(agent_name="test", key="k1")
        assert result == "测试内容"

    def test_recall_missing_key_returns_none(self, vm: VectorMemory) -> None:
        result = vm.recall(agent_name="test", key="not_exists")
        assert result is None

    def test_hybrid_search_basic(self, vm: VectorMemory) -> None:
        vm.store(agent_name="test", key="k1", content="EGFR TKI 肺癌靶向治疗")
        results = vm.hybrid_search(agent_name="test", query="肺癌")
        assert len(results) >= 1
        assert "score" in results[0]

    def test_cross_agent_search(self, vm: VectorMemory) -> None:
        vm.store(agent_name="agent_a", key="k1", content="共享数据", share_with=["*"])
        results = vm.search(agent_name="agent_b", query="共享", cross_agent=True)
        assert len(results) >= 1
        assert results[0]["content"] == "共享数据"

    def test_store_duplicate_key_replaces(self, vm: VectorMemory) -> None:
        vm.store(agent_name="test", key="dup", content="第一条")
        vm.store(agent_name="test", key="dup", content="第二条")
        results = vm.search(agent_name="test", query="第二")
        assert len(results) == 1
        assert results[0]["content"] == "第二条"
