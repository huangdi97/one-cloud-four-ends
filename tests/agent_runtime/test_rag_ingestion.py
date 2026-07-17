"""RAGIngestion & seed 集成测试 — 使用临时 SQLite 文件。"""

from __future__ import annotations

import logging
import os
import tempfile

import pytest

from cloud.app.agent_runtime.memory.rag_ingestion import RAGIngestion
from cloud.app.agent_runtime.memory.rag_seed_data import seed_demo_data
from cloud.app.agent_runtime.memory.vector_memory import VectorMemory


@pytest.fixture
def vm():
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    mem = VectorMemory(db_path=tmp_path)
    mem._model = None
    yield mem
    os.unlink(tmp_path)


@pytest.fixture
def ingestion(vm: VectorMemory) -> RAGIngestion:
    return RAGIngestion(vm)


class TestRAGIngestion:
    def test_ingest_from_text_and_search(self, ingestion: RAGIngestion) -> None:
        texts = ["EGFR-TKI治疗非小细胞肺癌", "PD-1抑制剂在肺癌中的应用"]
        ingestion.ingest_from_text(agent_name="test", texts=texts)
        results = ingestion.vm.search(agent_name="test", query="肺癌")
        assert len(results) >= 1

    def test_ingest_from_text_strict_zip(self, ingestion: RAGIngestion) -> None:
        texts = ["text1", "text2"]
        metadata = [{"a": 1}]
        with pytest.raises(ValueError):
            ingestion.ingest_from_text(agent_name="test", texts=texts, metadata=metadata)

    def test_seed_demo_data_creates_entries(self, vm: VectorMemory) -> None:
        seed_demo_data(vm)
        results = vm.search(agent_name="knowledge_worker", query="肺癌靶向", top_k=3)
        assert len(results) >= 1

    def test_ingest_from_db_nonexistent_table(self, ingestion: RAGIngestion, caplog) -> None:
        caplog.set_level(logging.WARNING)
        ingestion.ingest_from_db(agent_name="test", table_name="nonexistent_table", text_columns=["content"])
        assert any("does not exist" in msg for msg in caplog.messages)
