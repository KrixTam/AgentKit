"""agentkit/rag/file_memory_provider.py — SimpleRAG 默认文件记忆"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..memory.base import BaseMemoryProvider, Memory


class FileMemoryProvider(BaseMemoryProvider):
    """基于 JSON 文件的轻量持久化记忆。"""

    def __init__(self, file_path: str = ".agentkit/rag_memory.json") -> None:
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
        self._path.write_text(
            json.dumps(self._records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _to_memory(record: dict, *, score: float = 0.0) -> Memory:
        return Memory(
            id=str(record["id"]),
            content=str(record["content"]),
            metadata=dict(record.get("metadata", {})),
            created_at=record.get("created_at"),
            score=score,
        )

    async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
        self._counter += 1
        record = {
            "id": str(self._counter),
            "content": str(content),
            "user_id": user_id,
            "agent_id": agent_id,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
        }
        self._records.append(record)
        self._save()
        return [self._to_memory(record)]

    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        q_chars = set(str(query))
        ranked: list[tuple[float, dict]] = []
        for r in self._records:
            if user_id is not None and r.get("user_id") != user_id:
                continue
            if agent_id is not None and r.get("agent_id") != agent_id:
                continue
            content = str(r.get("content", ""))
            overlap = len(q_chars & set(content))
            if overlap <= 0:
                continue
            score = overlap / max(len(q_chars), 1)
            ranked.append((score, r))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [self._to_memory(r, score=s) for s, r in ranked[:limit]]

    async def get_all(self, *, user_id=None, agent_id=None):
        out: list[Memory] = []
        for r in self._records:
            if user_id is not None and r.get("user_id") != user_id:
                continue
            if agent_id is not None and r.get("agent_id") != agent_id:
                continue
            out.append(self._to_memory(r))
        return out

    async def delete(self, memory_id):
        before = len(self._records)
        self._records = [r for r in self._records if str(r.get("id")) != str(memory_id)]
        self._save()
        return len(self._records) < before
