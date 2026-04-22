import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, BaseMemoryProvider, Memory, Runner

MODEL = "gpt-4o"
MEMORY_FILE = "/tmp/agentkit_memory_standard.json"


class FileMemoryProvider(BaseMemoryProvider):
    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)
        self._records: list[dict] = []
        self._counter = 0
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._records = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._records = []
        if self._records:
            self._counter = max(int(r.get("id", 0)) for r in self._records)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._records, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _to_memory(record: dict) -> Memory:
        return Memory(id=str(record["id"]), content=str(record["content"]))

    async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
        self._counter += 1
        record = {
            "id": str(self._counter),
            "content": content,
            "user_id": user_id,
            "agent_id": agent_id,
            "metadata": metadata or {},
        }
        self._records.append(record)
        self._save()
        return [self._to_memory(record)]

    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        q = str(query).lower()
        matched: list[Memory] = []
        for record in self._records:
            if user_id is not None and record.get("user_id") != user_id:
                continue
            if agent_id is not None and record.get("agent_id") != agent_id:
                continue
            if q in str(record.get("content", "")).lower():
                matched.append(self._to_memory(record))
            if len(matched) >= limit:
                break
        return matched

    async def get_all(self, *, user_id=None, agent_id=None):
        out: list[Memory] = []
        for record in self._records:
            if user_id is not None and record.get("user_id") != user_id:
                continue
            if agent_id is not None and record.get("agent_id") != agent_id:
                continue
            out.append(self._to_memory(record))
        return out

    async def delete(self, memory_id):
        before = len(self._records)
        self._records = [r for r in self._records if str(r.get("id")) != str(memory_id)]
        self._save()
        return len(self._records) < before


async def main() -> None:
    print("=== 示例 8C：自定义 FileMemoryProvider（文件持久化） ===")
    memory = FileMemoryProvider(MEMORY_FILE)
    agent = Agent(
        name="file-memory-assistant",
        instructions="你是贴心助手。根据记忆回答，回答简洁。",
        model=MODEL,
        memory=memory,
        memory_async_write=False,
    )

    await Runner.run(agent, input="记住：我早餐喜欢美式咖啡。", user_id="user_001")
    result = await Runner.run(agent, input="推荐一杯饮料。", user_id="user_001")
    print("推荐:", result.final_output)
    print("持久化文件:", MEMORY_FILE)
    print("当前记忆数:", len(await memory.get_all(user_id="user_001")))


if __name__ == "__main__":
    asyncio.run(main())
