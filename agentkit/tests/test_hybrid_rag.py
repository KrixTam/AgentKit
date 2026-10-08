from __future__ import annotations

import asyncio
from pathlib import Path

from agentkit import HybridRAGAgent
from agentkit.rag.chunkers import RecursiveTokenChunker
from agentkit.rag.loaders import default_loaders
from agentkit.rag.retrievers import tokenize
from agentkit.rag.types import DocumentChunk, SearchHit


class FakeVectorStore:
    def __init__(self, vector_store_dir: str) -> None:
        self.vector_store_dir = vector_store_dir
        self._chunks: list[DocumentChunk] = []
        self._loaders = default_loaders()
        self._loader_by_suffix = {
            suffix: loader
            for loader in self._loaders
            for suffix in loader.suffixes
        }

    def reload_from_directory(self, *, knowledge_dir: str, chunker, embedder, supported_suffixes):
        base = Path(knowledge_dir)
        base.mkdir(parents=True, exist_ok=True)
        self._chunks = []
        for path in sorted(
            item for item in base.rglob("*") if item.is_file() and item.suffix.lower() in supported_suffixes
        ):
            loader = self._loader_by_suffix[path.suffix.lower()]
            content = loader.load(path)
            for idx, part in enumerate(chunker.split_text(content)):
                self._chunks.append(
                    DocumentChunk(
                        id=f"{path.name}-{idx}",
                        content=part,
                        source=str(path.relative_to(base)),
                        chunk_index=idx,
                        metadata={},
                    )
                )
        return list(self._chunks)

    def search(self, query: str, *, top_k: int, embedder):
        q_terms = set(tokenize(query))
        hits: list[SearchHit] = []
        for chunk in self._chunks:
            score = sum(1 for token in tokenize(chunk.content) if token in q_terms)
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    content=chunk.content,
                    source=chunk.source,
                    score=float(score),
                    chunk_index=chunk.chunk_index,
                    retriever="vector",
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]


class FakeReranker:
    model = "fake-reranker"

    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        q_terms = set(tokenize(query))
        scored: list[tuple[int, float]] = []
        for idx, doc in enumerate(documents):
            overlap = sum(2 for token in tokenize(doc) if token in q_terms)
            scored.append((idx, float(overlap + max(0, len(documents) - idx) * 0.01)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored


def test_hybrid_rag_load_and_search(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    (kb / "a.md").write_text("AgentKit 支持 Hybrid RAG 检索。", encoding="utf-8")
    (kb / "b.txt").write_text("AgentHub 提供注册发现与会话管理。", encoding="utf-8")

    rag = HybridRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="ollama/qwen3.5:4b",
        vector_store_dir=str(tmp_path / "vector"),
        memory_db_path=str(tmp_path / "memory.db"),
        vector_store=FakeVectorStore(str(tmp_path / "vector")),
        reranker=FakeReranker(),
    )

    hits = rag.search("Hybrid RAG 有什么能力")
    recall_hits = rag.search("Hybrid RAG 有什么能力", stage="recall")

    assert hits
    assert recall_hits
    assert hits[0].retriever == "reranker"
    assert "Hybrid RAG" in hits[0].content
    assert rag.list_knowledge_files() == ["a.md", "b.txt"]


def test_hybrid_rag_build_agent_and_memory_are_separate(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    (kb / "intro.md").write_text("HybridRAGAgent 默认拆分向量库与记忆库存储。", encoding="utf-8")

    vector_dir = tmp_path / "rag_v2" / "chroma"
    memory_db = tmp_path / "rag_v2" / "memory.db"

    rag = HybridRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="gpt-4o-mini",
        vector_store_dir=str(vector_dir),
        memory_db_path=str(memory_db),
        vector_store=FakeVectorStore(str(vector_dir)),
        reranker=FakeReranker(),
    )
    agent = rag.build_agent(name="hybrid-rag-test")

    asyncio.run(rag.memory.add("用户偏好本地检索", user_id="u1", agent_id="rag"))

    rag2 = HybridRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="gpt-4o-mini",
        vector_store_dir=str(vector_dir),
        memory_db_path=str(memory_db),
        vector_store=FakeVectorStore(str(vector_dir)),
        reranker=FakeReranker(),
    )
    memories = asyncio.run(rag2.memory.search("本地检索", user_id="u1", agent_id="rag"))

    assert agent.name == "hybrid-rag-test"
    assert agent.memory is not None
    assert rag.vector_store_dir() == str(vector_dir)
    assert rag.memory_db_path() == str(memory_db)
    assert memories
    assert memories[0].content == "用户偏好本地检索"


def test_hybrid_rag_respects_context_budget(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    text = (
        "第一段介绍 AgentKit 的 Hybrid RAG 检索。\n\n"
        "第二段继续说明 Hybrid RAG 的 reranker 工作方式。\n\n"
        "第三段补充 Hybrid RAG 的持久化与记忆拆分。"
    )
    (kb / "guide.md").write_text(text, encoding="utf-8")

    rag = HybridRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="gpt-4o-mini",
        vector_store_dir=str(tmp_path / "vector"),
        memory_db_path=str(tmp_path / "memory.db"),
        vector_store=FakeVectorStore(str(tmp_path / "vector")),
        reranker=FakeReranker(),
        chunker=RecursiveTokenChunker(chunk_size_tokens=18, chunk_overlap_tokens=4),
        final_top_k=3,
        max_context_tokens=25,
    )

    hits = rag.search("Hybrid RAG 的持久化和 reranker")
    assert hits
    assert len(hits) == 1
