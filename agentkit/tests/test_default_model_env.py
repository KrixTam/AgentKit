from __future__ import annotations

from pathlib import Path

from agentkit.llm.registry import LLMRegistry


def test_llmregistry_create_default_uses_env_from_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("AGENTKIT_OLLAMA_MODEL=qwen3.5:cloud\n", encoding="utf-8")

    llm = LLMRegistry.create_default()
    assert llm.__class__.__name__ == "OllamaAdapter"
    assert llm.config.model == "qwen3.5:cloud"

