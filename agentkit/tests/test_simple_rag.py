from __future__ import annotations

from pathlib import Path

from agentkit import SimpleRAGAgent


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


def test_simple_rag_build_agent_defaults(tmp_path: Path):
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    (kb / "intro.md").write_text("AgentKit 是一个 Python Agent 框架。", encoding="utf-8")

    memory_file = tmp_path / "rag_memory.json"
    rag = SimpleRAGAgent.from_directory(
        knowledge_dir=str(kb),
        model="gpt-4o-mini",
        memory_file=str(memory_file),
    )
    agent = rag.build_agent(name="test-rag")

    assert agent.name == "test-rag"
    assert agent.model == "gpt-4o-mini"
    assert agent.memory is not None
    assert len(agent.tools) == 2
