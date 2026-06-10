"""agentkit/rag/document_store.py — 本地文档加载与分块"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from .types import DocumentChunk, SimpleRAGConfig


class LocalDocumentStore:
    """本地文档存储：负责加载文件并切分为可检索 chunk。"""

    def __init__(self, config: SimpleRAGConfig):
        self.config = config
        self.chunks: list[DocumentChunk] = []

    def clear(self) -> None:
        self.chunks = []

    def load_documents(self) -> int:
        """加载知识库目录并完成分块，返回 chunk 数量。"""
        self.clear()
        base = Path(self.config.knowledge_dir)
        if not base.exists():
            base.mkdir(parents=True, exist_ok=True)
            return 0

        files: list[Path] = []
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in self.config.supported_suffixes:
                files.append(path)

        for filepath in sorted(files):
            content = filepath.read_text(encoding="utf-8", errors="ignore").strip()
            if not content:
                continue

            source = os.path.relpath(str(filepath), str(base))
            for idx, chunk_text in enumerate(self._split_text(content)):
                chunk_id = hashlib.md5(
                    f"{source}:{idx}:{chunk_text[:50]}".encode("utf-8")
                ).hexdigest()[:12]
                self.chunks.append(
                    DocumentChunk(
                        id=chunk_id,
                        content=chunk_text,
                        source=source,
                        chunk_index=idx,
                        metadata={},
                    )
                )
        return len(self.chunks)

    def list_sources(self) -> list[str]:
        return sorted({c.source for c in self.chunks})

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
