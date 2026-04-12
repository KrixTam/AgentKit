"""
示例 8：记忆系统 — 让 Agent 拥有跨会话长期记忆（Ollama 本地版）

演示三种记忆用法：
  A. 无记忆（默认）— 每次对话互相独立
  B. SimpleMemory（内置）— 轻量内存记忆，无需外部依赖，适合开发测试
  C. Mem0Provider（生产级）— 基于向量数据库的长期记忆（需安装 mem0ai + qdrant）

运行前请确保 Ollama 已启动：
  ollama serve
  ollama pull qwen3.5:cloud

运行：
  python examples/ollama/08_memory.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner, BaseMemoryProvider, Memory


MODEL = "ollama/qwen3.5:cloud"


# ============================================================
# SimpleMemory：轻量内存记忆实现（无需外部依赖）
#
# 适合开发和测试。进程退出后记忆丢失。
# 生产环境请使用 Mem0Provider（见示例 C）。
# ============================================================

class SimpleMemory(BaseMemoryProvider):
    """最简单的内存记忆实现——基于关键词匹配"""

    def __init__(self):
        self._store: list[Memory] = []
        self._counter = 0

    async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
        self._counter += 1
        m = Memory(id=str(self._counter), content=content)
        self._store.append(m)
        print(f"    💾 记忆已存储: {content[:60]}...")
        return [m]

    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        # 简单的关键词重叠匹配（生产环境应该用向量相似度搜索）
        query_words = set(query)
        scored = []
        for m in self._store:
            overlap = len(query_words & set(m.content))
            if overlap > 0:
                scored.append((overlap, m))
        scored.sort(reverse=True, key=lambda x: x[0])
        results = [m for _, m in scored[:limit]]
        if results:
            print(f"    🔍 检索到 {len(results)} 条相关记忆")
        return results

    async def get_all(self, *, user_id=None, agent_id=None):
        return list(self._store)

    async def delete(self, memory_id):
        self._store = [m for m in self._store if m.id != memory_id]
        return True


# ============================================================
# 演示 A：无记忆（默认）
# ============================================================

async def demo_no_memory():
    print("=" * 55)
    print("  A. 无记忆（默认）— 每次对话独立")
    print("=" * 55)

    agent = Agent(
        name="forgetful",
        instructions="你是一个简洁的助手。回答尽量简短。",
        model=MODEL,
    )

    # 第一次告诉它信息
    result = await Runner.run(agent, input="我叫小明，我喜欢喝咖啡")
    print(f"  对话1: {result.final_output}")

    # 第二次问它——它不会记得
    result = await Runner.run(agent, input="我叫什么名字？我喜欢喝什么？")
    print(f"  对话2: {result.final_output}")
    print("  📝 无记忆 → Agent 不记得之前的对话\n")


# ============================================================
# 演示 B：使用 SimpleMemory
# ============================================================

async def demo_simple_memory():
    print("=" * 55)
    print("  B. SimpleMemory — 轻量内存记忆")
    print("=" * 55)

    memory = SimpleMemory()

    agent = Agent(
        name="remembering",
        instructions="你是一个贴心的个人助手。根据相关记忆来个性化回答。回答简洁。",
        model=MODEL,
        memory=memory,
        memory_async_write=False,   # 多轮串行对话需要即时读取记忆
    )

    # 第一次对话：告诉它偏好
    print("\n  第1轮对话:")
    result = await Runner.run(agent, input="我叫小明，我喜欢喝咖啡，讨厌喝茶", user_id="user_001")
    print(f"  助手: {result.final_output}")

    # 第二次对话：它应该记住
    print("\n  第2轮对话:")
    result = await Runner.run(agent, input="帮我推荐一杯饮料吧", user_id="user_001")
    print(f"  助手: {result.final_output}")

    # 第三次对话：继续积累记忆
    print("\n  第3轮对话:")
    result = await Runner.run(agent, input="对了，我对牛奶过敏", user_id="user_001")
    print(f"  助手: {result.final_output}")

    # 第四次对话：看看它记住了多少
    print("\n  第4轮对话:")
    result = await Runner.run(agent, input="再给我推荐一杯饮料，要考虑我的情况", user_id="user_001")
    print(f"  助手: {result.final_output}")

    # 查看存储的所有记忆
    all_memories = await memory.get_all()
    print(f"\n  📋 记忆库中共 {len(all_memories)} 条记忆")


# ============================================================
# 演示 C：Mem0 说明（仅展示配置方式）
# ============================================================

def demo_mem0_info():
    print(f"\n{'=' * 55}")
    print("  C. Mem0Provider — 生产级长期记忆（配置说明）")
    print("=" * 55)

    print("""
  Mem0 提供向量数据库驱动的语义记忆，支持跨会话持久化。

  安装：
    pip install mem0ai
    docker run -p 6333:6333 qdrant/qdrant    # 启动向量数据库

  使用：
    from agentkit.memory.mem0_provider import Mem0Provider

    memory = Mem0Provider({
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "my_agent",
                "host": "localhost",
                "port": 6333,
            }
        }
    })

    agent = Agent(
        name="assistant",
        memory=memory,        # 就这一行
        ...
    )

  相比 SimpleMemory 的优势：
    ✅ 语义搜索（不是关键词匹配，而是理解意思）
    ✅ 持久化存储（重启不丢失）
    ✅ 自动记忆提取（从对话中智能抽取关键信息）
    ✅ 支持 user_id / agent_id 多维度隔离
""")


# ============================================================
# 主入口
# ============================================================

async def main():
    print("🚀 AgentKit 记忆系统演示\n")

    await demo_no_memory()
    await demo_simple_memory()
    demo_mem0_info()

    print("=" * 55)
    print("  演示完成 🎉")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
