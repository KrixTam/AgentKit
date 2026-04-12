"""
agentkit/memory/base.py — 记忆系统抽象接口
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Memory:
    """一条记忆"""
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    score: float = 0.0


class BaseMemoryProvider(ABC):
    """记忆提供者抽象接口"""

    @abstractmethod
    async def add(
        self, content: str, *, user_id: str | None = None,
        agent_id: str | None = None, metadata: dict | None = None,
    ) -> list[Memory]:
        ...

    @abstractmethod
    async def search(
        self, query: str, *, user_id: str | None = None,
        agent_id: str | None = None, limit: int = 10,
    ) -> list[Memory]:
        ...

    @abstractmethod
    async def get_all(
        self, *, user_id: str | None = None, agent_id: str | None = None,
    ) -> list[Memory]:
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        ...
