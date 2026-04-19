from __future__ import annotations

import importlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from agentkit.runner.context_store import ContextStore
from agentkit.runner.events import Event, EventType

from .models import SessionRecord, SessionStatus
from .stores.base import RegistryStore, SessionStore

logger = logging.getLogger("agenthub.runtime")


def load_entry(entry: str) -> Any:
    module_name, attr_name = entry.split(":", 1)
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    return value() if callable(value) else value


def resolve_session_status(event_type: str, current: SessionStatus) -> SessionStatus:
    if event_type == EventType.SUSPEND_REQUESTED:
        return SessionStatus.SUSPENDED
    if event_type == EventType.FINAL_OUTPUT:
        return SessionStatus.COMPLETED
    if event_type == EventType.ERROR:
        return SessionStatus.ERROR
    return current


class HubContextStore(ContextStore):
    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    def save(self, session_id: str, context: Any) -> None:
        self.session_store.save_checkpoint(session_id, context)

    def load(self, session_id: str, shared_context_cls: Any = None) -> Any:
        return self.session_store.load_checkpoint(session_id, shared_context_cls=shared_context_cls)

    def delete(self, session_id: str) -> None:
        self.session_store.delete_checkpoint(session_id)


@dataclass
class Metrics:
    requests_total: int = 0
    errors_total: int = 0
    suspended_total: int = 0
    completed_total: int = 0
    active_sessions: int = 0
    latency_ms: list[float] = field(default_factory=list)

    def observe(self, latency_ms: float, status: SessionStatus) -> None:
        self.requests_total += 1
        self.latency_ms.append(latency_ms)
        self.active_sessions = max(0, self.active_sessions + (1 if status == SessionStatus.RUNNING else -1))
        if status == SessionStatus.ERROR:
            self.errors_total += 1
        elif status == SessionStatus.SUSPENDED:
            self.suspended_total += 1
        elif status == SessionStatus.COMPLETED:
            self.completed_total += 1

    def to_prometheus(self) -> str:
        p95 = 0.0
        if self.latency_ms:
            sorted_ms = sorted(self.latency_ms)
            p95 = sorted_ms[int((len(sorted_ms) - 1) * 0.95)]
        lines = [
            f"agenthub_requests_total {self.requests_total}",
            f"agenthub_errors_total {self.errors_total}",
            f"agenthub_suspended_total {self.suspended_total}",
            f"agenthub_completed_total {self.completed_total}",
            f"agenthub_active_sessions {self.active_sessions}",
            f"agenthub_latency_p95_ms {p95:.3f}",
        ]
        return "\n".join(lines) + "\n"


@dataclass
class QuotaManager:
    max_concurrency_per_user: int
    rate_limit_per_minute: int
    _inflight: dict[str, int] = field(default_factory=dict)
    _bucket: dict[str, list[float]] = field(default_factory=dict)

    def acquire(self, key: str) -> None:
        now = time.time()
        inflight = self._inflight.get(key, 0)
        if inflight >= self.max_concurrency_per_user:
            raise ValueError("quota_exceeded:concurrency")
        timestamps = [t for t in self._bucket.get(key, []) if now - t < 60]
        if len(timestamps) >= self.rate_limit_per_minute:
            raise ValueError("quota_exceeded:rate")
        timestamps.append(now)
        self._bucket[key] = timestamps
        self._inflight[key] = inflight + 1

    def release(self, key: str) -> None:
        self._inflight[key] = max(0, self._inflight.get(key, 1) - 1)


def ensure_session(
    session_store: SessionStore,
    *,
    session_id: str | None,
    agent_name: str,
    agent_version: str,
    user_id: str | None,
    trace_id: str | None,
) -> SessionRecord:
    now = time.time()
    sid = session_id or str(uuid.uuid4())
    session = session_store.get(sid)
    if session is None:
        session = SessionRecord(
            session_id=sid,
            agent_name=agent_name,
            agent_version=agent_version,
            user_id=user_id,
            trace_id=trace_id,
            status=SessionStatus.RUNNING,
            created_at=now,
            updated_at=now,
            metadata={},
        )
        session_store.create(session)
    return session


def append_event_and_update(session_store: SessionStore, session_id: str, event: Event) -> SessionStatus:
    session_store.append_event(session_id, event.to_dict())
    current = session_store.get(session_id)
    if current is None:
        return SessionStatus.ERROR
    next_status = resolve_session_status(event.type, current.status)
    if next_status != current.status:
        session_store.update_status(session_id, next_status, str(event.data) if next_status == SessionStatus.ERROR else None)
    return next_status


def resolve_agent_from_registry(registry_store: RegistryStore, name: str, version_or_alias: str | None):
    manifest = registry_store.resolve(name, version_or_alias)
    if not manifest:
        raise ValueError(f"agent_not_found:{name}:{version_or_alias or 'latest'}")
    return manifest, load_entry(manifest.entry)
