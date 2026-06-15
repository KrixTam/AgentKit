"""agentkit/rag/document_store.py — 本地文档加载、增量构建与 SQLite 持久化。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .loaders import DocumentLoader, default_loaders
from .sqlite_store import connect
from .types import DocumentChunk, SimpleRAGConfig


class LocalDocumentStore:
    """本地文档存储：负责加载文件、切分 chunk，并落盘到 SQLite。"""

    def __init__(
        self,
        config: SimpleRAGConfig,
        *,
        loaders: list[DocumentLoader] | None = None,
    ):
        self.config = config
        self.chunks: list[DocumentChunk] = []
        self._loaders = loaders or default_loaders()
        self._loader_by_suffix = {
            suffix: loader
            for loader in self._loaders
            for suffix in loader.suffixes
        }

    def clear(self) -> None:
        self.chunks = []

    def load_documents(self) -> int:
        """加载知识库目录并完成增量持久化，返回 chunk 数量。"""
        self.clear()
        base = Path(self.config.knowledge_dir)
        if not base.exists():
            base.mkdir(parents=True, exist_ok=True)
            self._load_chunks_from_db()
            return 0

        files = sorted(
            path
            for path in base.rglob("*")
            if path.is_file() and path.suffix.lower() in self.config.supported_suffixes
        )
        live_sources = {os.path.relpath(str(path), str(base)) for path in files}

        with connect(self.config.storage_path) as conn:
            current_docs = {
                row["source"]: row["content_hash"]
                for row in conn.execute("SELECT source, content_hash FROM documents")
            }

            stale_sources = set(current_docs) - live_sources
            if stale_sources:
                conn.executemany("DELETE FROM documents WHERE source = ?", [(s,) for s in stale_sources])

            for filepath in files:
                source = os.path.relpath(str(filepath), str(base))
                content_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
                if current_docs.get(source) == content_hash:
                    continue

                loader = self._resolve_loader(filepath)
                content = loader.load(filepath)
                conn.execute("DELETE FROM documents WHERE source = ?", (source,))
                if not content:
                    continue

                chunks = self._split_text(content)
                timestamp = datetime.now(timezone.utc).isoformat()
                metadata = json.dumps({"suffix": filepath.suffix.lower()}, ensure_ascii=False)
                conn.execute(
                    """
                    INSERT INTO documents(source, absolute_path, content_hash, loader, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (source, str(filepath.resolve()), content_hash, loader.name, metadata, timestamp),
                )
                conn.executemany(
                    """
                    INSERT INTO chunks(id, source, chunk_index, content, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            self._chunk_id(source, idx, chunk_text),
                            source,
                            idx,
                            chunk_text,
                            "{}",
                        )
                        for idx, chunk_text in enumerate(chunks)
                    ],
                )
            conn.commit()

        self._load_chunks_from_db()
        return len(self.chunks)

    def list_sources(self) -> list[str]:
        return sorted({c.source for c in self.chunks})

    def storage_path(self) -> str:
        return self.config.storage_path

    def _load_chunks_from_db(self) -> None:
        with connect(self.config.storage_path) as conn:
            rows = conn.execute(
                "SELECT id, source, chunk_index, content, metadata FROM chunks ORDER BY source, chunk_index"
            ).fetchall()
        self.chunks = [
            DocumentChunk(
                id=row["id"],
                content=row["content"],
                source=row["source"],
                chunk_index=row["chunk_index"],
                metadata=json.loads(row["metadata"] or "{}"),
            )
            for row in rows
        ]

    def _resolve_loader(self, filepath: Path) -> DocumentLoader:
        suffix = filepath.suffix.lower()
        loader = self._loader_by_suffix.get(suffix)
        if loader is None:
            raise ValueError(f"不支持的文档类型: {suffix}")
        return loader

    @staticmethod
    def _chunk_id(source: str, chunk_index: int, content: str) -> str:
        return hashlib.md5(f"{source}:{chunk_index}:{content[:80]}".encode("utf-8")).hexdigest()[:12]

    def _split_text(self, text: str) -> list[str]:
        """按段落优先切块，超长段落再按字符窗切分。"""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            return [text[: self.config.chunk_size]]

        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 1 <= self.config.chunk_size:
                current = (current + "\n" + para).strip()
                continue

            if current:
                chunks.append(current)

            if len(para) <= self.config.chunk_size:
                current = para
                continue

            step = max(1, self.config.chunk_size - self.config.chunk_overlap)
            for i in range(0, len(para), step):
                part = para[i : i + self.config.chunk_size].strip()
                if part:
                    chunks.append(part)
            current = ""

        if current:
            chunks.append(current)
        return chunks
