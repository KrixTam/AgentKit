"""
agentkit/memory/mem0_provider.py — Mem0 记忆提供者
"""
from __future__ import annotations

from typing import Any

from .base import BaseMemoryProvider, Memory


class Mem0Provider(BaseMemoryProvider):
    """基于 Mem0 的记忆提供者"""

    def __init__(self, config: dict[str, Any] | None = None):
        try:
            from mem0 import Memory as Mem0Memory
        except ImportError:
            raise ImportError("请安装 mem0ai: pip install 'agentkit[memory]'")
        self._mem0 = Mem0Memory.from_config(config or self._default_config())

    async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
        messages = [{"role": "user", "content": content}]
        result = self._mem0.add(messages, user_id=user_id, agent_id=agent_id, metadata=metadata or {})
        return [Memory(id=r["id"], content=r["memory"]) for r in result.get("results", [])]

    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        results = self._mem0.search(query, user_id=user_id, agent_id=agent_id, limit=limit)
        return [
            Memory(id=r["id"], content=r["memory"], score=r.get("score", 0))
            for r in results.get("results", [])
        ]

    async def get_all(self, *, user_id=None, agent_id=None):
        results = self._mem0.get_all(user_id=user_id, agent_id=agent_id)
        return [Memory(id=r["id"], content=r["memory"]) for r in results.get("results", [])]

    async def delete(self, memory_id):
        self._mem0.delete(memory_id)
        return True

    @staticmethod
    def _default_config() -> dict:
        return {
            "vector_store": {
                "provider": "qdrant",
                "config": {"collection_name": "agent_memories", "host": "localhost", "port": 6333},
            },
        }
