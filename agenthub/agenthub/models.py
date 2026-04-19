from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionStatus(str, Enum):
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    ERROR = "error"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class AgentManifest(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=128)
    version: str = Field(..., min_length=1, max_length=64)
    entry: str = Field(..., description="Python entrypoint: module:attr")
    manifest_schema: dict[str, Any] = Field(default_factory=dict, alias="schema", serialization_alias="schema")
    runner_config: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @field_validator("entry")
    @classmethod
    def _validate_entry(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("entry 必须是 module:attr 格式")
        return value


class RegisterRequest(BaseModel):
    manifest: AgentManifest
    aliases: list[str] = Field(default_factory=list)


class InvokeRequest(BaseModel):
    input: str
    user_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    context: dict[str, Any] | None = None
    max_turns: int = 10


class ResumeRequest(BaseModel):
    user_input: str
    idempotency_key: str | None = None
    trace_id: str | None = None


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any = None


class SessionRecord(BaseModel):
    session_id: str
    agent_name: str
    agent_version: str
    user_id: str | None = None
    trace_id: str | None = None
    status: SessionStatus = SessionStatus.RUNNING
    error: str | None = None
    created_at: float
    updated_at: float
    metadata: dict[str, Any] = Field(default_factory=dict)
