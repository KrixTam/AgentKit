import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, BaseMemoryProvider, Memory, Runner

MODEL = "gpt-4o"


class SimpleMemory(BaseMemoryProvider):
    def __init__(self) -> None:
        self._store: list[Memory] = []
        self._counter = 0

    async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
        self._counter += 1
        item = Memory(id=str(self._counter), content=content)
        self._store.append(item)
        return [item]

    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        query_chars = set(query)
        scored: list[tuple[int, Memory]] = []
        for item in self._store:
            overlap = len(query_chars & set(item.content))
            if overlap > 0:
                scored.append((overlap, item))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [m for _, m in scored[:limit]]

    async def get_all(self, *, user_id=None, agent_id=None):
        return list(self._store)

    async def delete(self, memory_id):
        self._store = [m for m in self._store if m.id != memory_id]
        return True


async def main() -> None:
    print("=== 示例 8A：SimpleMemory ===")
    memory = SimpleMemory()
    agent = Agent(
        name="remembering",
        instructions="你是贴心助手。根据记忆回答，回答简洁。",
        model=MODEL,
        memory=memory,
        memory_async_write=False,
    )

    await Runner.run(agent, input="我叫小明，喜欢咖啡，讨厌茶。", user_id="user_001")
    result = await Runner.run(agent, input="帮我推荐一杯饮料。", user_id="user_001")
    print("推荐:", result.final_output)
    print("记忆条数:", len(await memory.get_all()))


if __name__ == "__main__":
    asyncio.run(main())
