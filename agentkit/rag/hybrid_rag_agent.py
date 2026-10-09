"""agentkit/rag/hybrid_rag_agent.py — HybridRAGAgent 核心实现。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..agents.agent import Agent
from ..llm.base import BaseLLM
from ..llm.types import LLMConfig
from ..memory.base import BaseMemoryProvider
from ..tools.function_tool import FunctionTool, function_tool
from .chroma_store import ChromaVectorStore
from .chunkers import RecursiveTokenChunker
from .file_memory_provider import SQLiteMemoryProvider
from .hybrid_types import HybridRAGConfig, HybridSearchStage
from .providers import Embedder, OllamaEmbeddingProvider, OllamaReranker, Reranker
from .retrievers import BM25Retriever
from .types import SearchHit


class HybridRAGAgent:
    """增强版本地 RAG：BM25 + Chroma 向量检索 + RRF + Reranker。"""

    def __init__(
        self,
        *,
        model: str | LLMConfig | BaseLLM,
        config: HybridRAGConfig | None = None,
        memory_provider: BaseMemoryProvider | None = None,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        vector_store: ChromaVectorStore | None = None,
        chunker: RecursiveTokenChunker | None = None,
        enable_memory: bool | None = None,
        memory_db_path: str | None = None,
    ) -> None:
        self.model = model
        self.config = config or HybridRAGConfig()
        if enable_memory is not None:
            self.config.enable_memory = enable_memory
        if memory_db_path is not None:
            self.config.memory_db_path = memory_db_path

        self.chunker = chunker or RecursiveTokenChunker(
            chunk_size_tokens=self.config.chunk_size_tokens,
            chunk_overlap_tokens=self.config.chunk_overlap_tokens,
        )
        self.embedder = embedder or OllamaEmbeddingProvider(
            model=self.config.embedding_model,
            api_base=self.config.embedding_base_url,
            timeout=self.config.provider_timeout,
        )
        self.reranker = reranker or OllamaReranker(
            model=self.config.reranker_model,
            api_base=self.config.reranker_base_url,
            timeout=self.config.provider_timeout,
        )
        self.vector_store = vector_store or ChromaVectorStore(
            vector_store_dir=self.config.vector_store_dir,
            collection_name=self.config.collection_name,
            embedding_model=self.config.embedding_model,
        )
        self._bm25 = BM25Retriever(k1=self.config.bm25_k1, b=self.config.bm25_b)
        self._chunks = []

        self.memory: BaseMemoryProvider | None
        if memory_provider is not None:
            self.memory = memory_provider
        elif self.config.enable_memory:
            self.memory = SQLiteMemoryProvider(self.config.memory_db_path)
        else:
            self.memory = None
        self.reload()

    @classmethod
    def from_directory(
        cls,
        *,
        knowledge_dir: str,
        model: str | LLMConfig | BaseLLM,
        vector_store_dir: str | None = None,
        memory_db_path: str | None = None,
        embedding_model: str | None = None,
        reranker_model: str | None = None,
        chunk_size_tokens: int = 350,
        chunk_overlap_tokens: int = 50,
        recall_top_k: int = 20,
        final_top_k: int = 3,
        max_context_tokens: int | None = None,
        enable_memory: bool = True,
        embedding_base_url: str | None = None,
        reranker_base_url: str | None = None,
        memory_provider: BaseMemoryProvider | None = None,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        vector_store: ChromaVectorStore | None = None,
        chunker: RecursiveTokenChunker | None = None,
    ) -> "HybridRAGAgent":
        defaults = HybridRAGConfig()
        cfg = HybridRAGConfig(
            knowledge_dir=knowledge_dir,
            vector_store_dir=vector_store_dir or defaults.vector_store_dir,
            memory_db_path=memory_db_path or defaults.memory_db_path,
            collection_name=defaults.collection_name,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            recall_top_k=recall_top_k,
            final_top_k=final_top_k,
            max_context_tokens=max_context_tokens,
            supported_suffixes=defaults.supported_suffixes,
            enable_memory=enable_memory,
            embedding_model=embedding_model or defaults.embedding_model,
            reranker_model=reranker_model or defaults.reranker_model,
            embedding_base_url=embedding_base_url,
            reranker_base_url=reranker_base_url,
            bm25_k1=defaults.bm25_k1,
            bm25_b=defaults.bm25_b,
            rrf_k=defaults.rrf_k,
            provider_timeout=defaults.provider_timeout,
        )
        return cls(
            model=model,
            config=cfg,
            memory_provider=memory_provider,
            embedder=embedder,
            reranker=reranker,
            vector_store=vector_store,
            chunker=chunker,
            enable_memory=enable_memory,
            memory_db_path=memory_db_path,
        )

    def reload(self) -> int:
        self._chunks = self.vector_store.reload_from_directory(
            knowledge_dir=self.config.knowledge_dir,
            chunker=self.chunker,
            embedder=self.embedder,
            supported_suffixes=self.config.supported_suffixes,
        )
        self._bm25.build(self._chunks)
        return len(self._chunks)

    def list_knowledge_files(self) -> list[str]:
        return sorted({chunk.source for chunk in self._chunks})

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        stage: HybridSearchStage = "final",
    ) -> list[SearchHit]:
        if stage == "recall":
            limit = top_k or self.config.recall_top_k
            return self._recall(query, top_k=limit)

        recall_hits = self._recall(query, top_k=self.config.recall_top_k)
        limit = top_k or self.config.final_top_k
        return self._rerank(query, recall_hits, top_k=limit)

    def vector_store_dir(self) -> str:
        return self.config.vector_store_dir

    def memory_db_path(self) -> str:
        return self.config.memory_db_path

    def _recall(self, query: str, *, top_k: int) -> list[SearchHit]:
        bm25_hits = self._bm25.search(query, top_k=top_k)
        vector_hits = self.vector_store.search(query, top_k=top_k, embedder=self.embedder)

        ranked_lists = {
            "bm25": bm25_hits,
            "vector": vector_hits,
        }
        merged: dict[tuple[str, int, str], dict[str, Any]] = defaultdict(dict)
        for retriever_name, hits in ranked_lists.items():
            for rank, hit in enumerate(hits, start=1):
                key = (hit.source, hit.chunk_index, hit.content)
                entry = merged[key]
                entry["source"] = hit.source
                entry["chunk_index"] = hit.chunk_index
                entry["content"] = hit.content
                entry["score"] = entry.get("score", 0.0) + 1.0 / (self.config.rrf_k + rank)
                entry.setdefault("retrievers", []).append(retriever_name)

        recall_hits = [
            SearchHit(
                content=entry["content"],
                source=entry["source"],
                score=float(entry["score"]),
                chunk_index=int(entry["chunk_index"]),
                retriever="hybrid",
            )
            for entry in merged.values()
        ]
        recall_hits.sort(key=lambda item: item.score, reverse=True)
        return recall_hits[:top_k]

    def _rerank(self, query: str, recall_hits: list[SearchHit], *, top_k: int) -> list[SearchHit]:
        if not recall_hits or top_k <= 0:
            return []
        try:
            ranked = self.reranker.rerank(query, [hit.content for hit in recall_hits])
        except RuntimeError:
            # 某些本地部署仅支持 embedding / generation，不暴露 rerank 接口；
            # 此时回退到混合召回结果，避免整条检索链路不可用。
            return self._trim_by_context_budget(recall_hits[:top_k])
        hits_by_index = {idx: score for idx, score in ranked}

        reranked: list[SearchHit] = []
        for idx, hit in enumerate(recall_hits):
            if idx not in hits_by_index:
                continue
            reranked.append(
                SearchHit(
                    content=hit.content,
                    source=hit.source,
                    score=hits_by_index[idx],
                    chunk_index=hit.chunk_index,
                    retriever="reranker",
                )
            )
        reranked.sort(key=lambda item: item.score, reverse=True)
        return self._trim_by_context_budget(reranked[:top_k])

    def _trim_by_context_budget(self, hits: list[SearchHit]) -> list[SearchHit]:
        if not hits or self.config.max_context_tokens is None:
            return hits

        total = 0
        trimmed: list[SearchHit] = []
        for hit in hits:
            cost = self.chunker.count_tokens(hit.content)
            if trimmed and total + cost > self.config.max_context_tokens:
                break
            total += cost
            trimmed.append(hit)
        return trimmed or hits[:1]

    def as_tools(self) -> list[FunctionTool]:
        @function_tool
        def search_knowledge_base(query: str) -> str:
            """从知识库中检索与查询最相关的文档内容。"""
            hits = self.search(query)
            if not hits:
                return "未找到与查询相关的文档内容。"
            parts: list[str] = []
            for i, hit in enumerate(hits, 1):
                parts.append(
                    f"【文档 {i}】(来源: {hit.source}, 相关度: {round(hit.score, 4)})\n{hit.content}"
                )
            return "\n\n---\n\n".join(parts)

        @function_tool
        def list_knowledge_files() -> str:
            """列出知识库中的所有文档文件。"""
            sources = self.list_knowledge_files()
            if not sources:
                return "知识库为空。"
            lines = [f"📚 知识库共有 {len(sources)} 个文档:"]
            for source in sources:
                count = sum(1 for chunk in self._chunks if chunk.source == source)
                lines.append(f"  📄 {source} ({count} 个文档块)")
            return "\n".join(lines)

        return [search_knowledge_base, list_knowledge_files]

    def build_agent(
        self,
        *,
        name: str = "hybrid-rag-assistant",
        instructions: str | None = None,
        tool_use_behavior: str = "run_llm_again",
        memory_async_write: bool = False,
        **kwargs: Any,
    ) -> Agent:
        final_instructions = instructions or self.default_instructions()
        return Agent(
            name=name,
            instructions=final_instructions,
            model=self.model,
            tools=self.as_tools(),
            memory=self.memory,
            tool_use_behavior=tool_use_behavior,
            memory_async_write=memory_async_write,
            **kwargs,
        )

    @staticmethod
    def default_instructions() -> str:
        return (
            "你是一个智能知识助手。\n"
            "1) 当用户问题需要文档依据时，优先调用 search_knowledge_base。\n"
            "2) 检索链路默认包含混合召回与重排，请基于命中的文档回答。\n"
            "3) 回答要优先结合注入的相关记忆与知识库检索结果，尽量注明来源。\n"
            "4) 如检索不到相关信息，请明确说明“不确定/未命中知识库”，不要编造。"
        )
