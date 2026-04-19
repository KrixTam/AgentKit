from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agentkit.runner.context import RunContext

from ..models import AgentManifest, SessionRecord, SessionStatus


class RegistryStore(ABC):
    @abstractmethod
    def register(self, manifest: AgentManifest, aliases: list[str] | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def unregister(self, name: str, version: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_versions(self, name: str) -> list[AgentManifest]:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[AgentManifest]:
        raise NotImplementedError

    @abstractmethod
    def resolve(self, name: str, version_or_alias: str | None = None) -> AgentManifest | None:
        raise NotImplementedError

    @abstractmethod
    def set_alias(self, name: str, alias: str, version: str) -> None:
        raise NotImplementedError


class SessionStore(ABC):
    @abstractmethod
    def create(self, session: SessionRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, session_id: str) -> SessionRecord | None:
        raise NotImplementedError

    @abstractmethod
    def update_status(self, session_id: str, status: SessionStatus, error: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(self, status: SessionStatus | None = None) -> list[SessionRecord]:
        raise NotImplementedError

    @abstractmethod
    def append_event(self, session_id: str, event: dict[str, Any]) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_checkpoint(self, session_id: str, context: RunContext) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_checkpoint(self, session_id: str, shared_context_cls: Any = None) -> RunContext | None:
        raise NotImplementedError

    @abstractmethod
    def delete_checkpoint(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def terminate(self, session_id: str) -> None:
        raise NotImplementedError
