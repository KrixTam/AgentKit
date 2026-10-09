from __future__ import annotations

import os
from pathlib import Path

from agentkit._hybrid_rag_init import HybridRAGWorkspaceConfig, _build_config_from_wizard, generate_workspace, main


def test_generate_workspace_creates_expected_files(tmp_path: Path):
    config = HybridRAGWorkspaceConfig(
        target_dir=tmp_path / "workspace",
        knowledge_dir="knowledge_base",
        vector_store_dir=".agentkit/rag_v2/chroma",
        memory_db_path=".agentkit/rag_v2/memory.db",
        model="qwen/qwen3.6-flash",
        embedding_model="ollama/qllama/bge-small-zh-v1.5:f16",
        reranker_model="ollama/qllama/bce-reranker-base_v1:f16",
        embedding_base_url=None,
        reranker_base_url=None,
        chunk_size_tokens=350,
        chunk_overlap_tokens=50,
        recall_top_k=20,
        final_top_k=3,
        max_context_tokens=None,
        enable_memory=True,
        agent_name="demo-hybrid-rag",
        create_sample_doc=True,
    )

    written = generate_workspace(config)

    expected = {
        config.target_dir / ".env",
        config.target_dir / ".env.example",
        config.target_dir / "README.md",
        config.target_dir / "create_agent.py",
        config.target_dir / "start_rerank_server.py",
        config.target_dir / "chat.py",
        config.target_dir / "knowledge_base" / "welcome.md",
    }
    assert expected.issubset(set(written))
    assert (config.target_dir / ".agentkit" / "rag_v2").is_dir()

    env_text = (config.target_dir / ".env").read_text(encoding="utf-8")
    assert "AGENTKIT_HYBRID_RAG_MODEL=qwen/qwen3.6-flash" in env_text
    assert "AGENTKIT_HYBRID_RAG_VECTOR_STORE_DIR=.agentkit/rag_v2/chroma" in env_text

    create_agent_text = (config.target_dir / "create_agent.py").read_text(encoding="utf-8")
    assert "HybridRAGAgent.from_directory" in create_agent_text
    assert 'def resolve_knowledge_dir() -> str:' in create_agent_text
    assert 'knowledge_dir=resolve_knowledge_dir(),' in create_agent_text

    rerank_script_text = (config.target_dir / "start_rerank_server.py").read_text(encoding="utf-8")
    assert "from agentkit.rag.rerank_server import main as rerank_server_main" in rerank_script_text
    assert 'print("启动 AgentKit 本地 rerank sidecar")' in rerank_script_text

    chat_text = (config.target_dir / "chat.py").read_text(encoding="utf-8")
    assert 'if files == ["welcome.md"]:' in chat_text
    assert "不包含真实业务知识" in chat_text
    assert 'print(f"知识库目录: {knowledge_dir}")' in chat_text
    assert "os.environ[key.strip()] = value.strip()" in create_agent_text

    readme_text = (config.target_dir / "README.md").read_text(encoding="utf-8")
    assert "`start_rerank_server.py`" in readme_text
    assert "python start_rerank_server.py" in readme_text


def test_main_interactive_creates_workspace_with_defaults(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    inputs = iter([
        "",
        "",
        "",
        "",
        "",
        "n",
        "",
        "",
        "",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    exit_code = main(["--skip-self-check"])

    assert exit_code == 0
    workspace = tmp_path / "hybrid-rag-workspace"
    assert (workspace / ".env").exists()
    assert (workspace / "chat.py").exists()

    output = capsys.readouterr().out
    assert "已生成以下文件" in output
    assert "python chat.py" in output
    assert "python start_rerank_server.py" in output


def test_workspace_env_file_overrides_existing_shell_env(tmp_path: Path, monkeypatch):
    config = HybridRAGWorkspaceConfig(
        target_dir=tmp_path / "workspace",
        knowledge_dir="/Users/krix/Downloads/Test/archives_v2",
        vector_store_dir=".agentkit/rag_v2/chroma",
        memory_db_path=".agentkit/rag_v2/memory.db",
        model="ollama/qwen3.5:4b",
        embedding_model="ollama/qllama/bge-small-zh-v1.5:f16",
        reranker_model="ollama/qllama/bce-reranker-base_v1:f16",
        embedding_base_url=None,
        reranker_base_url=None,
        chunk_size_tokens=350,
        chunk_overlap_tokens=50,
        recall_top_k=20,
        final_top_k=3,
        max_context_tokens=None,
        enable_memory=True,
        agent_name="demo-hybrid-rag",
        create_sample_doc=False,
    )
    generate_workspace(config)

    monkeypatch.setenv("AGENTKIT_HYBRID_RAG_KNOWLEDGE_DIR", "knowledge_base")
    namespace: dict[str, object] = {"__file__": str(create_agent_path := config.target_dir / "create_agent.py")}
    exec(create_agent_path.read_text(encoding="utf-8"), namespace)

    resolved = namespace["resolve_knowledge_dir"]()

    assert resolved == "/Users/krix/Downloads/Test/archives_v2"
    assert os.environ["AGENTKIT_HYBRID_RAG_KNOWLEDGE_DIR"] == "/Users/krix/Downloads/Test/archives_v2"


def test_wizard_preserves_absolute_knowledge_dir(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inputs = iter([
        "",
        "/Users/krix/Downloads/Test/archives_v2",
        "",
        "",
        "",
        "n",
        "n",
        "",
        "",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    config = _build_config_from_wizard()

    assert config.knowledge_dir == "/Users/krix/Downloads/Test/archives_v2"


def test_generate_workspace_keeps_absolute_knowledge_dir_in_env(tmp_path: Path):
    config = HybridRAGWorkspaceConfig(
        target_dir=tmp_path / "workspace",
        knowledge_dir="/Users/krix/Downloads/Test/archives_v2",
        vector_store_dir=".agentkit/rag_v2/chroma",
        memory_db_path=".agentkit/rag_v2/memory.db",
        model="ollama/qwen3.5:4b",
        embedding_model="ollama/qllama/bge-small-zh-v1.5:f16",
        reranker_model="ollama/qllama/bce-reranker-base_v1:f16",
        embedding_base_url=None,
        reranker_base_url=None,
        chunk_size_tokens=350,
        chunk_overlap_tokens=50,
        recall_top_k=20,
        final_top_k=3,
        max_context_tokens=None,
        enable_memory=True,
        agent_name="demo-hybrid-rag",
        create_sample_doc=False,
    )

    generate_workspace(config)

    env_text = (config.target_dir / ".env").read_text(encoding="utf-8")
    assert "AGENTKIT_HYBRID_RAG_KNOWLEDGE_DIR=/Users/krix/Downloads/Test/archives_v2" in env_text
