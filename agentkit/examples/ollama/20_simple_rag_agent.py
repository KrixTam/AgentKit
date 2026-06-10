"""
示例 20：SimpleRAGAgent（Ollama 本地版）

运行前：
  ollama serve
  ollama pull qwen3.5:4b
  mkdir -p ./knowledge_base
  echo "AgentKit 支持 Tool、Skill、Memory 与多模型适配。" > ./knowledge_base/intro.txt
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Runner, SimpleRAGAgent
from model_config import resolve_model


def main() -> None:
    rag = SimpleRAGAgent.from_directory(
        knowledge_dir="./knowledge_base",
        model=resolve_model("qwen3.5:4b"),
        top_k=3,
    )
    agent = rag.build_agent(name="simple-rag-ollama")
    result = Runner.run_sync(agent, input="AgentKit 有哪些核心能力？")
    print("✅ 回复:", result.final_output)


if __name__ == "__main__":
    main()
