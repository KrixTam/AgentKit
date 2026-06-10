"""agentkit/rag/types.py — SimpleRAG 类型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RetrieverKind = Literal["tfidf", "bm25", "vector", "hybrid"]


@dataclass
class DocumentChunk:
    """知识库切块后的文档单元。"""

    id: str
    content: str
    source: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchHit:
    """检索命中结果。"""

    content: str
    source: str
    score: float
    chunk_index: int
    retriever: str


@dataclass
class SimpleRAGConfig:
    """SimpleRAGAgent 基础配置。"""

    knowledge_dir: str = "./knowledge_base"
    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k: int = 3
    supported_suffixes: tuple[str, ...] = (".txt", ".md", ".markdown")
    default_retriever: RetrieverKind = "hybrid"
    hybrid_weights: dict[str, float] = field(
        default_factory=lambda: {"tfidf": 0.4, "bm25": 0.4, "vector": 0.2}
    )
