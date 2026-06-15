"""agentkit/rag/sqlite_store.py — SimpleRAG 的 SQLite 存储辅助。"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: str) -> sqlite3.Connection:
    """创建启用外键与行字典访问的 SQLite 连接。"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    """初始化 SimpleRAG 所需表结构。"""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            source TEXT PRIMARY KEY,
            absolute_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            loader TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(source) REFERENCES documents(source) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_source_chunk
        ON chunks(source, chunk_index);

        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            agent_id TEXT,
            content TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_memories_user_agent
        ON memories(user_id, agent_id, created_at DESC);
        """
    )
    conn.commit()
