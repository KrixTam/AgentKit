"""agentkit/rag/hybrid_types.py — HybridRAGAgent 类型定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


HybridSearchStage = Literal["recall", "final"]


@dataclass
class HybridRAGConfig:
    """HybridRAGAgent 基础配置。"""

    knowledge_dir: str = "./knowledge_base"
    vector_store_dir: str = ".agentkit/rag_v2/chroma"
    memory_db_path: str = ".agentkit/rag_v2/memory.db"
    collection_name: str = "hybrid_rag"
    chunk_size_tokens: int = 350
    chunk_overlap_tokens: int = 50
    recall_top_k: int = 20
    final_top_k: int = 3
    max_context_tokens: int | None = None
    supported_suffixes: tuple[str, ...] = (".txt", ".md", ".markdown", ".pdf")
    enable_memory: bool = True
    embedding_model: str = "ollama/qllama/bge-small-zh-v1.5:f16"
    reranker_model: str = "ollama/qllama/bce-reranker-base_v1:f16"
    embedding_base_url: str | None = None
    reranker_base_url: str | None = None
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    rrf_k: int = 60
    provider_timeout: int = 300
