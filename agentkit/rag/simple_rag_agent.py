"""agentkit/rag/simple_rag_agent.py — SimpleRAGAgent 核心实现"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..agents.agent import Agent
from ..llm.base import BaseLLM
from ..llm.types import LLMConfig
from ..memory.base import BaseMemoryProvider
from ..tools.function_tool import FunctionTool, function_tool
from .document_store import LocalDocumentStore
from .file_memory_provider import SQLiteMemoryProvider
from .retrievers import BM25Retriever, TfidfRetriever, VectorRetriever
from .types import RetrieverKind, SearchHit, SimpleRAGConfig


class SimpleRAGAgent:
    """轻量 RAG 构建器：本地文档检索 + 默认 SQLite 记忆 + 标准 Agent 输出。"""

    def __init__(
        self,
        *,
        model: str | LLMConfig | BaseLLM,
        config: SimpleRAGConfig | None = None,
        memory_provider: BaseMemoryProvider | None = None,
        storage_path: str | None = None,
        enable_memory: bool | None = None,
        memory_file: str | None = None,
    ) -> None:
        self.model = model
        self.config = config or SimpleRAGConfig()
        if storage_path is not None:
            self.config.storage_path = storage_path
        elif memory_file is not None:
            # 兼容旧参数；底层已统一迁移到 SQLite 存储。
            self.config.storage_path = memory_file
        if enable_memory is not None:
            self.config.enable_memory = enable_memory
        self.store = LocalDocumentStore(self.config)

        self._retrievers = {
            "tfidf": TfidfRetriever(),
            "bm25": BM25Retriever(),
            "vector": VectorRetriever(),
        }

        self.memory: BaseMemoryProvider | None
        if memory_provider is not None:
            self.memory = memory_provider
        elif self.config.enable_memory:
            self.memory = SQLiteMemoryProvider(self.config.storage_path)
        else:
            self.memory = None
        self.reload()

    @classmethod
    def from_directory(
        cls,
        *,
        knowledge_dir: str,
        model: str | LLMConfig | BaseLLM,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        top_k: int = 3,
        default_retriever: RetrieverKind = "hybrid",
        storage_path: str = ".agentkit/rag/index.db",
        enable_memory: bool = True,
        memory_file: str | None = None,
        memory_provider: BaseMemoryProvider | None = None,
    ) -> "SimpleRAGAgent":
        cfg = SimpleRAGConfig(
            knowledge_dir=knowledge_dir,
            storage_path=storage_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            top_k=top_k,
            default_retriever=default_retriever,
            enable_memory=enable_memory,
        )
        return cls(
            model=model,
            config=cfg,
            storage_path=storage_path,
            memory_file=memory_file,
            enable_memory=enable_memory,
            memory_provider=memory_provider,
        )

    def reload(self) -> int:
        """重新加载知识库并重建三种检索索引。"""
        count = self.store.load_documents()
        for retriever in self._retrievers.values():
            retriever.build(self.store.chunks)
        return count

    def list_knowledge_files(self) -> list[str]:
        return self.store.list_sources()

    def storage_path(self) -> str:
        return self.store.storage_path()

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        retriever: RetrieverKind | None = None,
    ) -> list[SearchHit]:
        top_k = top_k or self.config.top_k
        retriever = retriever or self.config.default_retriever
        if retriever == "hybrid":
            return self._hybrid_search(query, top_k=top_k)
        return self._single_search(query, top_k=top_k, retriever=retriever)

    def _single_search(self, query: str, *, top_k: int, retriever: RetrieverKind) -> list[SearchHit]:
        if retriever not in self._retrievers:
            raise ValueError(f"不支持的检索器: {retriever}")
        return self._retrievers[retriever].search(query, top_k=top_k)

    def _hybrid_search(self, query: str, *, top_k: int) -> list[SearchHit]:
        hits_by_source: dict[tuple[str, int, str], list[SearchHit]] = defaultdict(list)
        for name in ("tfidf", "bm25", "vector"):
            for hit in self._retrievers[name].search(query, top_k=top_k * 3):
                key = (hit.source, hit.chunk_index, hit.content)
                hits_by_source[key].append(hit)

        w = self.config.hybrid_weights
        merged: list[SearchHit] = []
        for (source, chunk_index, content), hits in hits_by_source.items():
            score_by_retriever = {h.retriever: h.score for h in hits}
            score = (
                w.get("tfidf", 0.0) * score_by_retriever.get("tfidf", 0.0)
                + w.get("bm25", 0.0) * score_by_retriever.get("bm25", 0.0)
                + w.get("vector", 0.0) * score_by_retriever.get("vector", 0.0)
            )
            merged.append(
                SearchHit(
                    content=content,
                    source=source,
                    score=score,
                    chunk_index=chunk_index,
                    retriever="hybrid",
                )
            )
        merged.sort(key=lambda x: x.score, reverse=True)
        return merged[:top_k]

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
                count = sum(1 for c in self.store.chunks if c.source == source)
                lines.append(f"  📄 {source} ({count} 个文档块)")
            return "\n".join(lines)

        return [search_knowledge_base, list_knowledge_files]

    def build_agent(
        self,
        *,
        name: str = "simple-rag-assistant",
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
            "2) 可调用 list_knowledge_files 帮助用户了解知识库范围。\n"
            "3) 回答要优先结合注入的相关记忆与知识库检索结果，尽量注明来源。\n"
            "4) 如检索不到相关信息，请明确说明“不确定/未命中知识库”，不要编造。"
        )
