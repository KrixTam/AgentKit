"""agentkit/rag/file_memory_provider.py — SimpleRAG 默认 SQLite 记忆。"""

from __future__ import annotations

import json
from datetime import datetime

from ..memory.base import BaseMemoryProvider, Memory
from .retrievers import tokenize
from .sqlite_store import connect


class SQLiteMemoryProvider(BaseMemoryProvider):
    """基于 SQLite 的轻量持久化记忆。"""

    def __init__(self, db_path: str = ".agentkit/rag/index.db") -> None:
        self._db_path = db_path

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
        created_at = datetime.now().isoformat()
        record = {
            "content": str(content),
            "user_id": user_id,
            "agent_id": agent_id,
            "metadata": metadata or {},
            "created_at": created_at,
        }
        with connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO memories(user_id, agent_id, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, agent_id, record["content"], json.dumps(record["metadata"], ensure_ascii=False), created_at),
            )
            conn.commit()
            record["id"] = str(cursor.lastrowid)
        return [self._to_memory(record)]

    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        records = self._query_records(user_id=user_id, agent_id=agent_id)
        query_tokens = tokenize(str(query))
        query_set = set(query_tokens) if query_tokens else set(str(query))
        ranked: list[tuple[float, dict]] = []
        for record in records:
            content = str(record.get("content", ""))
            content_tokens = tokenize(content)
            content_set = set(content_tokens) if content_tokens else set(content)
            overlap = len(query_set & content_set)
            if overlap <= 0:
                continue
            score = overlap / max(len(query_set), 1)
            ranked.append((score, record))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [self._to_memory(record, score=score) for score, record in ranked[:limit]]

    async def get_all(self, *, user_id=None, agent_id=None):
        return [self._to_memory(record) for record in self._query_records(user_id=user_id, agent_id=agent_id)]

    async def delete(self, memory_id):
        with connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (str(memory_id),))
            conn.commit()
            return cursor.rowcount > 0

    def _query_records(self, *, user_id=None, agent_id=None) -> list[dict]:
        clauses: list[str] = []
        params: list[str | None] = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)

        sql = "SELECT id, user_id, agent_id, content, metadata, created_at FROM memories"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC, id DESC"

        with connect(self._db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": str(row["id"]),
                "content": row["content"],
                "user_id": row["user_id"],
                "agent_id": row["agent_id"],
                "metadata": json.loads(row["metadata"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


class FileMemoryProvider(SQLiteMemoryProvider):
    """向后兼容别名：保留旧名字，内部已改为 SQLite 实现。"""
