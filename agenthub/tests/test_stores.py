from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentkit.runner.context import RunContext

from agenthub.models import AgentManifest, SessionRecord, SessionStatus
from agenthub.stores.memory import InMemoryRegistryStore, InMemorySessionStore
from agenthub.stores.sqlite import SQLiteRegistryStore, SQLiteSessionStore


def _manifest() -> AgentManifest:
    return AgentManifest(
        name="demo-agent",
        version="1.0.0",
        entry="example.module:create_agent",
        manifest_schema={"type": "object"},
        runner_config={"max_turns": 8},
        tags=["demo", "stable"],
    )


def test_registry_store_memory_alias_latest():
    store = InMemoryRegistryStore()
    m1 = _manifest()
    m2 = m1.model_copy(update={"version": "1.1.0"})
    store.register(m1, aliases=["stable"])
    store.register(m2, aliases=["latest"])
    assert store.resolve("demo-agent", "stable").version == "1.0.0"
    assert store.resolve("demo-agent", "latest").version == "1.1.0"


def test_registry_store_sqlite_persist():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        store = SQLiteRegistryStore(f.name)
        store.register(_manifest(), aliases=["stable"])
        reloaded = SQLiteRegistryStore(f.name)
        assert reloaded.resolve("demo-agent", "stable") is not None


def test_session_store_parity_memory_and_sqlite():
    now = time.time()
    session = SessionRecord(
        session_id="s1",
        agent_name="demo-agent",
        agent_version="1.0.0",
        user_id="u1",
        trace_id="t1",
        status=SessionStatus.RUNNING,
        created_at=now,
        updated_at=now,
    )
    mem = InMemorySessionStore()
    mem.create(session)
    mem.append_event("s1", {"type": "llm_response", "data": {"content": "ok"}})
    ctx = RunContext(input="hello", user_id="u1", session_id="s1")
    mem.save_checkpoint("s1", ctx)
    assert mem.load_checkpoint("s1").session_id == "s1"

    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        sql = SQLiteSessionStore(f.name)
        sql.create(session)
        sql.append_event("s1", {"type": "llm_response", "data": {"content": "ok"}})
        sql.save_checkpoint("s1", ctx)
        assert sql.load_checkpoint("s1").session_id == "s1"
        assert len(sql.list_events("s1")) == 1
