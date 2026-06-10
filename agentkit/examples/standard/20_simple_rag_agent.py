"""
示例 20：SimpleRAGAgent（标准版）

运行前：
  export OPENAI_API_KEY="sk-..."
  mkdir -p ./knowledge_base
  echo "AgentKit 是一个 Python 原生 Agent 框架。" > ./knowledge_base/intro.txt
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Runner, SimpleRAGAgent
from model_config import resolve_model


def create_agent():
    rag = SimpleRAGAgent.from_directory(
        knowledge_dir="./knowledge_base",
        model=resolve_model("gpt-4o-mini"),
        top_k=3,
    )
    return rag.build_agent(name="simple-rag-standard")


def main() -> None:
    agent = create_agent()
    result = Runner.run_sync(agent, input="AgentKit 是什么？")
    print("✅ 回复:", result.final_output)


if __name__ == "__main__":
    main()
