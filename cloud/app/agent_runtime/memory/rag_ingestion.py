"""RAG数据导入引擎，从多种来源批量注入向量记忆库。"""

import json
import logging

logger = logging.getLogger(__name__)


class RAGIngestion:
    """RAG数据导入引擎，支持从数据库/JSON/纯文本批量注入。"""

    def __init__(self, vector_memory, batch_size: int = 32):
        self.vm = vector_memory
        self.batch_size = batch_size

    def ingest_from_db(
        self,
        agent_name: str,
        table_name: str,
        text_columns: list[str],
        metadata_columns: list[str] | None = None,
        share_with: list[str] | None = None,
    ):
        """从SQLite表读取文本字段，批量生成embedding写入vector_memory。"""
        metadata_columns = metadata_columns or []
        conn = self.vm._get_connection()
        # 表名白名单校验
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        if not existing:
            logger.warning("Table %s does not exist, skipping ingestion", table_name)
            return
        # 列名白名单校验：只保留目标表中存在的列
        valid_cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name!r})").fetchall()}
        requested_cols = set(text_columns + metadata_columns)
        safe_cols = requested_cols & valid_cols
        rejected = requested_cols - valid_cols
        for col in rejected:
            logger.warning("Column %s not found in table %s, skipping", col, table_name)
        if not safe_cols:
            logger.warning("No valid columns for table %s, skipping ingestion", table_name)
            return
        cols = ", ".join(sorted(safe_cols))
        offset = 0
        while True:
            page = conn.execute(
                f"SELECT rowid, {cols} FROM [{table_name}] LIMIT ? OFFSET ?",
                (self.batch_size, offset),
            ).fetchall()
            if not page:
                break
            batch = []
            for row in page:
                row_dict = dict(row)
                content_parts = [str(row_dict.get(c, "")) for c in text_columns]
                content = " ".join(p for p in content_parts if p)
                metadata = {c: row_dict.get(c, "") for c in metadata_columns}
                key = f"{table_name}:{row_dict['rowid']}"
                batch.append((agent_name, key, content, metadata, share_with))
                if len(batch) >= self.batch_size:
                    self._flush(batch)
                    batch = []
            if batch:
                self._flush(batch)
            offset += self.batch_size
        logger.info("Ingested records from table %s", table_name)

    def ingest_from_json(
        self,
        agent_name: str,
        json_path: str,
        text_field: str,
        metadata_fields: list[str] | None = None,
        share_with: list[str] | None = None,
    ):
        """从JSON文件批量导入。"""
        metadata_fields = metadata_fields or []
        with open(json_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        if isinstance(records, dict):
            records = [records]
        batch = []
        for i, record in enumerate(records):
            content = str(record.get(text_field, ""))
            metadata = {f: record.get(f, "") for f in metadata_fields}
            key = f"json:{i}"
            batch.append((agent_name, key, content, metadata, share_with))
            if len(batch) >= self.batch_size:
                self._flush(batch)
                batch = []
        if batch:
            self._flush(batch)
        logger.info("Ingested %d records from %s", len(records), json_path)

    def ingest_from_text(
        self,
        agent_name: str,
        texts: list,
        metadata: list | None = None,
        share_with: list[str] | None = None,
    ):
        """直接从文本列表导入。"""
        metadata = metadata or [{}] * len(texts)
        batch = []
        for i, (text, meta) in enumerate(zip(texts, metadata, strict=True)):
            key = f"text:{i}"
            batch.append((agent_name, key, str(text), meta, share_with))
            if len(batch) >= self.batch_size:
                self._flush(batch)
                batch = []
        if batch:
            self._flush(batch)
        logger.info("Ingested %d text records", len(texts))

    def _flush(self, batch: list):
        for agent_name, key, content, metadata, share_with in batch:
            self.vm.store(agent_name, key, content, metadata, share_with)
