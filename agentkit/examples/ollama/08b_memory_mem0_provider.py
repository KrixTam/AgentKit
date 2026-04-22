import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner

MODEL = "ollama/qwen3.5:cloud"


async def main() -> None:
    print("=== 示例 8B：Mem0Provider ===")
    try:
        from agentkit.memory.mem0_provider import Mem0Provider
    except Exception:
        print("未安装 mem0ai，跳过运行。")
        print("安装: pip install mem0ai")
        print("并启动 qdrant: docker run -p 6333:6333 qdrant/qdrant")
        return

    if not os.getenv("OPENAI_API_KEY"):
        print("未设置 OPENAI_API_KEY，跳过运行。")
        return

    try:
        memory = Mem0Provider(
            {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "collection_name": "agentkit_quickstart",
                        "host": "localhost",
                        "port": 6333,
                    },
                }
            }
        )
    except Exception as exc:
        print(f"Mem0 初始化失败，跳过运行: {exc}")
        return

    agent = Agent(
        name="mem0-assistant",
        instructions="你是贴心助手。根据记忆回答，回答简洁。",
        model=MODEL,
        memory=memory,
        memory_async_write=False,
    )

    await Runner.run(agent, input="记住：我喜欢低糖拿铁。", user_id="user_001")
    result = await Runner.run(agent, input="给我推荐一杯饮料。", user_id="user_001")
    print("推荐:", result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
