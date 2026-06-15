from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from agentkit import SimpleRAGAgent
from agentkit.rag.loaders import PdfLoader


def test_simple_rag_load_and_search(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    (kb / "a.md").write_text("AgentKit 支持 Tool 与 Skill。", encoding="utf-8")
    (kb / "b.txt").write_text("AgentHub 提供注册发现与会话管理。", encoding="utf-8")

    rag = SimpleRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="ollama/qwen3.5:4b",
        top_k=2,
    )

    hits = rag.search("AgentKit 有什么能力", retriever="hybrid")
    assert hits
    assert any("AgentKit" in h.content for h in hits)
    assert Path(rag.storage_path()).exists()


def test_simple_rag_build_agent_defaults(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    (kb / "intro.md").write_text("AgentKit 是一个 Python Agent 框架。", encoding="utf-8")

    storage_path = tmp_path / ".agentkit" / "rag" / "index.db"
    rag = SimpleRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="gpt-4o-mini",
        storage_path=str(storage_path),
    )
    agent = rag.build_agent(name="test-rag")

    assert agent.name == "test-rag"
    assert agent.model == "gpt-4o-mini"
    assert agent.memory is not None
    assert len(agent.tools) == 2


def test_simple_rag_persists_chunks_and_memory(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    (kb / "intro.md").write_text("AgentKit 支持 RAG 与 Memory。", encoding="utf-8")

    storage_path = tmp_path / ".agentkit" / "rag" / "index.db"
    rag = SimpleRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="gpt-4o-mini",
        storage_path=str(storage_path),
    )
    asyncio.run(rag.memory.add("用户喜欢咖啡", user_id="u1", agent_id="rag"))

    rag2 = SimpleRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="gpt-4o-mini",
        storage_path=str(storage_path),
    )

    hits = rag2.search("RAG", retriever="tfidf")
    memories = asyncio.run(rag2.memory.search("咖啡", user_id="u1", agent_id="rag"))

    assert hits
    assert memories
    assert memories[0].content == "用户喜欢咖啡"

    with sqlite3.connect(storage_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 1


def test_simple_rag_supports_pdf_loader(tmp_path: Path, monkeypatch):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    pdf_path = kb / "guide.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    monkeypatch.setattr(
        PdfLoader,
        "_extract_text",
        lambda self, path: "SimpleRAGAgent 现在支持 PDF 作为知识库输入。",
    )

    rag = SimpleRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="ollama/qwen3.5:4b",
    )

    hits = rag.search("PDF 输入源", retriever="bm25")
    assert hits
    assert hits[0].source == "guide.pdf"


def test_simple_rag_can_disable_memory(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    (kb / "a.txt").write_text("关闭记忆时仍可检索知识库。", encoding="utf-8")

    rag = SimpleRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="gpt-4o-mini",
        enable_memory=False,
    )
    agent = rag.build_agent(name="rag-no-memory")

    assert rag.memory is None
    assert agent.memory is None
