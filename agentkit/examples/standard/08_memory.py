"""
示例 8：记忆系统 — 让 Agent 拥有跨会话长期记忆（标准版）

演示三种记忆用法：
  A. 无记忆（默认）
  B. SimpleMemory（轻量内存记忆）
  C. Mem0Provider（生产级）

运行前请设置环境变量：
  export OPENAI_API_KEY="sk-..."

运行：
  python examples/standard/08_memory.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner, BaseMemoryProvider, Memory


# ============================================================
# SimpleMemory：轻量内存记忆（无需外部依赖）
# ============================================================

class SimpleMemory(BaseMemoryProvider):
    """最简单的内存记忆实现"""

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
# 演示 A：无记忆
# ============================================================

async def demo_no_memory():
    print("=" * 55)
    print("  A. 无记忆（默认）— 每次对话独立")
    print("=" * 55)

    agent = Agent(
        name="forgetful",
        instructions="你是一个简洁的助手。回答尽量简短。",
        model="gpt-4o",
    )

    result = await Runner.run(agent, input="我叫小明，我喜欢喝咖啡")
    print(f"  对话1: {result.final_output}")

    result = await Runner.run(agent, input="我叫什么名字？我喜欢喝什么？")
    print(f"  对话2: {result.final_output}")
    print("  📝 无记忆 → Agent 不记得之前的对话\n")


# ============================================================
# 演示 B：SimpleMemory
# ============================================================

async def demo_simple_memory():
    print("=" * 55)
    print("  B. SimpleMemory — 轻量内存记忆")
    print("=" * 55)

    memory = SimpleMemory()

    agent = Agent(
        name="remembering",
        instructions="你是一个贴心的个人助手。根据相关记忆来个性化回答。回答简洁。",
        model="gpt-4o",
        memory=memory,
        memory_async_write=False,   # 多轮串行对话需要即时读取记忆
    )

    print("\n  第1轮:")
    result = await Runner.run(agent, input="我叫小明，我喜欢喝咖啡，讨厌喝茶", user_id="user_001")
    print(f"  助手: {result.final_output}")

    print("\n  第2轮:")
    result = await Runner.run(agent, input="帮我推荐一杯饮料吧", user_id="user_001")
    print(f"  助手: {result.final_output}")

    print("\n  第3轮:")
    result = await Runner.run(agent, input="对了，我对牛奶过敏", user_id="user_001")
    print(f"  助手: {result.final_output}")

    print("\n  第4轮:")
    result = await Runner.run(agent, input="再给我推荐一杯饮料，要考虑我的情况", user_id="user_001")
    print(f"  助手: {result.final_output}")

    all_memories = await memory.get_all()
    print(f"\n  📋 记忆库中共 {len(all_memories)} 条记忆")


# ============================================================
# 主入口
# ============================================================

async def main():
    print("🚀 AgentKit 记忆系统演示\n")
    await demo_no_memory()
    await demo_simple_memory()

    print(f"\n{'=' * 55}")
    print("  演示完成 🎉")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
