"""
示例 21：HybridRAGAgent（标准版）

运行前：
  export OPENAI_API_KEY="sk-..."
  ollama serve
  ollama pull qllama/bge-small-zh-v1.5:f16
  # reranker 需使用兼容 /api/rerank 或 /v1/rerank 的本地服务
  mkdir -p ./knowledge_base
  echo "AgentKit 是一个 Python 原生 Agent 框架。" > ./knowledge_base/intro.txt
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import HybridRAGAgent
from model_config import resolve_model


def create_agent():
    rag = HybridRAGAgent.from_directory(
        knowledge_dir=os.getenv("AGENTKIT_HYBRID_RAG_KNOWLEDGE_DIR", "./knowledge_base"),
        model=resolve_model(os.getenv("AGENTKIT_HYBRID_RAG_MODEL", "gpt-4o-mini")),
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
        recall_top_k=int(os.getenv("AGENTKIT_HYBRID_RAG_RECALL_TOP_K", "20")),
        final_top_k=int(os.getenv("AGENTKIT_HYBRID_RAG_FINAL_TOP_K", "3")),
    )
    return rag.build_agent(name="hybrid-rag-standard")


def main() -> None:
    agent = create_agent()
    result = agent.invoke(input="AgentKit 是什么？")
    print("✅ 回复:", result.final_output)


if __name__ == "__main__":
    main()
