from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

from agentkit.runner.context import RunContext

from ..models import AgentManifest, SessionRecord, SessionStatus
from .base import RegistryStore, SessionStore


class SQLiteMixin:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (id INTEGER PRIMARY KEY, version TEXT UNIQUE, applied_at REAL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS registry (name TEXT, version TEXT, manifest_json TEXT, PRIMARY KEY(name, version))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS aliases (name TEXT, alias TEXT, version TEXT, PRIMARY KEY(name, alias))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                "session_id TEXT PRIMARY KEY, agent_name TEXT, agent_version TEXT, user_id TEXT, trace_id TEXT,"
                "status TEXT, error TEXT, metadata_json TEXT, created_at REAL, updated_at REAL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "session_id TEXT, seq INTEGER, event_json TEXT, PRIMARY KEY(session_id, seq))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS session_event_seq (session_id TEXT PRIMARY KEY, last_seq INTEGER NOT NULL DEFAULT 0)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS checkpoints (session_id TEXT PRIMARY KEY, context_json TEXT, updated_at REAL)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id, seq)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(id, version, applied_at) VALUES(1, 'v1', ?)",
                (time.time(),),
            )


class SQLiteRegistryStore(SQLiteMixin, RegistryStore):
    def register(self, manifest: AgentManifest, aliases: list[str] | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO registry(name, version, manifest_json) VALUES(?, ?, ?)",
                (manifest.name, manifest.version, manifest.model_dump_json()),
            )
            if aliases:
                for alias in aliases:
                    conn.execute(
                        "INSERT OR REPLACE INTO aliases(name, alias, version) VALUES(?, ?, ?)",
                        (manifest.name, alias, manifest.version),
                    )

    def unregister(self, name: str, version: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM registry WHERE name=? AND version=?", (name, version))
            conn.execute("DELETE FROM aliases WHERE name=? AND version=?", (name, version))

    def list_versions(self, name: str) -> list[AgentManifest]:
        with self._conn() as conn:
            rows = conn.execute("SELECT manifest_json FROM registry WHERE name=? ORDER BY version", (name,)).fetchall()
        return [AgentManifest.model_validate_json(r["manifest_json"]) for r in rows]

    def list_all(self) -> list[AgentManifest]:
        with self._conn() as conn:
            rows = conn.execute("SELECT manifest_json FROM registry ORDER BY name, version").fetchall()
        return [AgentManifest.model_validate_json(r["manifest_json"]) for r in rows]

    def resolve(self, name: str, version_or_alias: str | None = None) -> AgentManifest | None:
        version_or_alias = version_or_alias or "latest"
        with self._conn() as conn:
            row = conn.execute(
                "SELECT manifest_json FROM registry WHERE name=? AND version=?",
                (name, version_or_alias),
            ).fetchone()
            if row:
                return AgentManifest.model_validate_json(row["manifest_json"])
            alias_row = conn.execute(
                "SELECT version FROM aliases WHERE name=? AND alias=?",
                (name, version_or_alias),
            ).fetchone()
            if alias_row:
                row = conn.execute(
                    "SELECT manifest_json FROM registry WHERE name=? AND version=?",
                    (name, alias_row["version"]),
                ).fetchone()
                if row:
                    return AgentManifest.model_validate_json(row["manifest_json"])
            if version_or_alias == "latest":
                row = conn.execute(
                    "SELECT manifest_json FROM registry WHERE name=? ORDER BY version DESC LIMIT 1",
                    (name,),
                ).fetchone()
                if row:
                    return AgentManifest.model_validate_json(row["manifest_json"])
        return None

    def set_alias(self, name: str, alias: str, version: str) -> None:
        with self._conn() as conn:
            exists = conn.execute(
                "SELECT 1 FROM registry WHERE name=? AND version=?",
                (name, version),
            ).fetchone()
            if not exists:
                raise ValueError(f"版本不存在: {name}:{version}")
            conn.execute(
                "INSERT OR REPLACE INTO aliases(name, alias, version) VALUES(?, ?, ?)",
                (name, alias, version),
            )


class SQLiteSessionStore(SQLiteMixin, SessionStore):
    def create(self, session: SessionRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions(session_id, agent_name, agent_version, user_id, trace_id, status, error, metadata_json, created_at, updated_at)"
                " VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session.session_id,
                    session.agent_name,
                    session.agent_version,
                    session.user_id,
                    session.trace_id,
                    session.status.value,
                    session.error,
                    json.dumps(session.metadata, ensure_ascii=False),
                    session.created_at,
                    session.updated_at,
                ),
            )

    def get(self, session_id: str) -> SessionRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if not row:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            agent_name=row["agent_name"],
            agent_version=row["agent_version"],
            user_id=row["user_id"],
            trace_id=row["trace_id"],
            status=SessionStatus(row["status"]),
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def update_status(self, session_id: str, status: SessionStatus, error: str | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET status=?, error=?, updated_at=? WHERE session_id=?",
                (status.value, error, time.time(), session_id),
            )

    def list_sessions(self, status: SessionStatus | None = None) -> list[SessionRecord]:
        sql = "SELECT * FROM sessions"
        params: tuple[Any, ...] = ()
        if status is not None:
            sql += " WHERE status=?"
            params = (status.value,)
        sql += " ORDER BY created_at DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            SessionRecord(
                session_id=r["session_id"],
                agent_name=r["agent_name"],
                agent_version=r["agent_version"],
                user_id=r["user_id"],
                trace_id=r["trace_id"],
                status=SessionStatus(r["status"]),
                error=r["error"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                metadata=json.loads(r["metadata_json"] or "{}"),
            )
            for r in rows
        ]

    def append_event(self, session_id: str, event: dict[str, Any]) -> int:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO session_event_seq(session_id, last_seq) VALUES(?, 0)",
                (session_id,),
            )
            conn.execute(
                "UPDATE session_event_seq SET last_seq = last_seq + 1 WHERE session_id=?",
                (session_id,),
            )
            row = conn.execute(
                "SELECT last_seq FROM session_event_seq WHERE session_id=?",
                (session_id,),
            ).fetchone()
            seq = int(row["last_seq"])
            conn.execute(
                "INSERT INTO events(session_id, seq, event_json) VALUES(?, ?, ?)",
                (session_id, seq, json.dumps(event, ensure_ascii=False)),
            )
            return seq

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT seq, event_json FROM events WHERE session_id=? ORDER BY seq ASC",
                (session_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["event_json"])
            result.append({"seq": row["seq"], **payload})
        return result

    def save_checkpoint(self, session_id: str, context: RunContext) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints(session_id, context_json, updated_at) VALUES(?, ?, ?)",
                (session_id, context.to_json(), time.time()),
            )

    def load_checkpoint(self, session_id: str, shared_context_cls: Any = None) -> RunContext | None:
        with self._conn() as conn:
            row = conn.execute("SELECT context_json FROM checkpoints WHERE session_id=?", (session_id,)).fetchone()
        if not row:
            return None
        return RunContext.from_json(row["context_json"], shared_context_cls=shared_context_cls)

    def delete_checkpoint(self, session_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM checkpoints WHERE session_id=?", (session_id,))

    def terminate(self, session_id: str) -> None:
        self.update_status(session_id, SessionStatus.TERMINATED, "terminated_by_user")
        self.delete_checkpoint(session_id)
