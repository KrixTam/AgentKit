"""
示例 21：HybridRAGAgent（Ollama 本地版）

运行前：
  ollama serve
  ollama pull qwen3.5:4b
  ollama pull qllama/bge-small-zh-v1.5:f16
  ollama pull qllama/bce-reranker-base_v1:f16
  agentkit-rerank-server --model qllama/bce-reranker-base_v1:f16
  mkdir -p ./knowledge_base
  echo "AgentKit 支持 Tool、Skill、Memory 与多模型适配。" > ./knowledge_base/intro.txt
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import HybridRAGAgent
from model_config import resolve_model


def main() -> None:
    rag = HybridRAGAgent.from_directory(
        knowledge_dir=os.getenv("AGENTKIT_HYBRID_RAG_KNOWLEDGE_DIR", "./knowledge_base"),
        model=resolve_model(os.getenv("AGENTKIT_HYBRID_RAG_MODEL", "qwen3.5:4b")),
        vector_store_dir=os.getenv("AGENTKIT_HYBRID_RAG_VECTOR_STORE_DIR", "./.agentkit/rag_v2/chroma"),
        memory_db_path=os.getenv("AGENTKIT_HYBRID_RAG_MEMORY_DB_PATH", "./.agentkit/rag_v2/memory.db"),
        embedding_model=os.getenv(
            "AGENTKIT_HYBRID_RAG_EMBEDDING_MODEL",
            "ollama/qllama/bge-small-zh-v1.5:f16",
        ),
        reranker_model=os.getenv(
            "AGENTKIT_HYBRID_RAG_RERANKER_MODEL",
            "ollama/qllama/bce-reranker-base_v1:f16",
        ),
        reranker_base_url=os.getenv("AGENTKIT_HYBRID_RAG_RERANKER_BASE_URL", "http://127.0.0.1:11535"),
        recall_top_k=int(os.getenv("AGENTKIT_HYBRID_RAG_RECALL_TOP_K", "20")),
        final_top_k=int(os.getenv("AGENTKIT_HYBRID_RAG_FINAL_TOP_K", "3")),
    )
    agent = rag.build_agent(name="hybrid-rag-ollama")
    result = agent.invoke(input="AgentKit 有哪些核心能力？")
    print("✅ 回复:", result.final_output)


if __name__ == "__main__":
    main()
