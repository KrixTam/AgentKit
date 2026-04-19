from __future__ import annotations

import time
from typing import Any

from agentkit.runner.context import RunContext

from ..models import AgentManifest, SessionRecord, SessionStatus
from .base import RegistryStore, SessionStore


class InMemoryRegistryStore(RegistryStore):
    def __init__(self):
        self._data: dict[str, dict[str, AgentManifest]] = {}
        self._aliases: dict[str, dict[str, str]] = {}

    def register(self, manifest: AgentManifest, aliases: list[str] | None = None) -> None:
        self._data.setdefault(manifest.name, {})[manifest.version] = manifest
        if aliases:
            for alias in aliases:
                self.set_alias(manifest.name, alias, manifest.version)

    def unregister(self, name: str, version: str) -> None:
        self._data.get(name, {}).pop(version, None)
        if name in self._aliases:
            for k, v in list(self._aliases[name].items()):
                if v == version:
                    self._aliases[name].pop(k, None)

    def list_versions(self, name: str) -> list[AgentManifest]:
        return sorted(self._data.get(name, {}).values(), key=lambda x: x.version)

    def list_all(self) -> list[AgentManifest]:
        items: list[AgentManifest] = []
        for versions in self._data.values():
            items.extend(versions.values())
        return sorted(items, key=lambda x: (x.name, x.version))

    def resolve(self, name: str, version_or_alias: str | None = None) -> AgentManifest | None:
        versions = self._data.get(name, {})
        if not versions:
            return None
        if not version_or_alias:
            version_or_alias = "latest"
        if version_or_alias in versions:
            return versions[version_or_alias]
        alias_target = self._aliases.get(name, {}).get(version_or_alias)
        if alias_target:
            return versions.get(alias_target)
        if version_or_alias == "latest":
            return sorted(versions.values(), key=lambda x: x.version)[-1]
        return None

    def set_alias(self, name: str, alias: str, version: str) -> None:
        if version not in self._data.get(name, {}):
            raise ValueError(f"版本不存在: {name}:{version}")
        self._aliases.setdefault(name, {})[alias] = version


class InMemorySessionStore(SessionStore):
    def __init__(self):
        self._sessions: dict[str, SessionRecord] = {}
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._checkpoints: dict[str, RunContext] = {}
        self._seq: dict[str, int] = {}

    def create(self, session: SessionRecord) -> None:
        self._sessions[session.session_id] = session
        self._events.setdefault(session.session_id, [])
        self._seq.setdefault(session.session_id, 0)

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def update_status(self, session_id: str, status: SessionStatus, error: str | None = None) -> None:
        session = self._sessions[session_id]
        session.status = status
        session.error = error
        session.updated_at = time.time()

    def list_sessions(self, status: SessionStatus | None = None) -> list[SessionRecord]:
        sessions = list(self._sessions.values())
        if status is not None:
            sessions = [s for s in sessions if s.status == status]
        return sorted(sessions, key=lambda x: x.created_at, reverse=True)

    def append_event(self, session_id: str, event: dict[str, Any]) -> int:
        seq = self._seq[session_id] + 1
        self._seq[session_id] = seq
        self._events[session_id].append({"seq": seq, **event})
        return seq

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._events.get(session_id, []))

    def save_checkpoint(self, session_id: str, context: RunContext) -> None:
        self._checkpoints[session_id] = RunContext.from_dict(context.to_dict())

    def load_checkpoint(self, session_id: str, shared_context_cls: Any = None) -> RunContext | None:
        ctx = self._checkpoints.get(session_id)
        if ctx is None:
            return None
        return RunContext.from_dict(ctx.to_dict(), shared_context_cls=shared_context_cls)

    def delete_checkpoint(self, session_id: str) -> None:
        self._checkpoints.pop(session_id, None)

    def terminate(self, session_id: str) -> None:
        self.update_status(session_id, SessionStatus.TERMINATED, "terminated_by_user")
        self.delete_checkpoint(session_id)
