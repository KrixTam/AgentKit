"""
agentkit/runner/context.py — RunContext（一次运行的完整上下文）
"""
from __future__ import annotations

import copy
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SuspensionRecord:
    suspension_id: str
    tool_call_id: str
    tool_name: str
    prompt: str
    form_schema: dict[str, Any] | None = None
    resume_strategy: str = "as_tool_result"
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None
    resolved_input: str | None = None


@dataclass
class RunContext:
    """一次运行的完整上下文"""
    input: str
    shared_context: Any = None

    # 用户标识（用于记忆隔离）
    user_id: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid4()))

    # 对话消息
    messages: list[dict[str, Any]] = field(default_factory=list)

    # 状态
    state: dict[str, Any] = field(default_factory=dict)

    # 分支（并行 Agent 用）
    branch: Optional[str] = None
    # 挂起记录（框架托管，业务侧无需关注内部协议）
    suspensions: list[SuspensionRecord] = field(default_factory=list)
    # resume 幂等记录：idempotency_key -> 已处理结果
    resume_idempotency: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_message(self, role: str, content: Any) -> None:
        self.messages.append({"role": role, "content": content})

    def add_tool_result(self, tool_call_id: str, result: Any) -> None:
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(result),
        })

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self.messages)

    def create_branch(self, branch_name: str) -> "RunContext":
        branch_ctx = copy.deepcopy(self)
        branch_ctx.branch = branch_name
        return branch_ctx

    def register_suspension(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        prompt: str,
        form_schema: dict[str, Any] | None = None,
        resume_strategy: str = "as_tool_result",
    ) -> SuspensionRecord:
        record = SuspensionRecord(
            suspension_id=str(uuid4()),
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            prompt=prompt,
            form_schema=form_schema,
            resume_strategy=resume_strategy,
        )
        self.suspensions.append(record)
        return record

    def get_pending_suspension(self, suspension_id: str | None = None) -> SuspensionRecord | None:
        pending = [s for s in self.suspensions if s.resolved_at is None]
        if not pending:
            return None
        if suspension_id:
            for s in pending:
                if s.suspension_id == suspension_id:
                    return s
            return None
        return pending[-1]

    def resolve_suspension(self, suspension_id: str, user_input: str) -> SuspensionRecord | None:
        for s in self.suspensions:
            if s.suspension_id == suspension_id and s.resolved_at is None:
                s.resolved_at = time.time()
                s.resolved_input = user_input
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        """将 RunContext 序列化为字典，支持 shared_context 自定义协议"""
        serialized_shared = None
        if self.shared_context is not None:
            if hasattr(self.shared_context, "__ak_serialize__"):
                serialized_shared = self.shared_context.__ak_serialize__()
            elif hasattr(self.shared_context, "to_dict"):
                serialized_shared = self.shared_context.to_dict()
            else:
                try:
                    # 尝试基础 JSON 序列化
                    json.dumps(self.shared_context)
                    serialized_shared = self.shared_context
                except (TypeError, ValueError):
                    logger.warning(f"shared_context of type {type(self.shared_context)} is not serializable. Skipping.")
                    serialized_shared = None

        return {
            "input": self.input,
            "shared_context": serialized_shared,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "messages": copy.deepcopy(self.messages),
            "state": copy.deepcopy(self.state),
            "branch": self.branch,
            "suspensions": [asdict(s) for s in self.suspensions],
            "resume_idempotency": copy.deepcopy(self.resume_idempotency),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], shared_context_cls: Optional[Any] = None) -> "RunContext":
        """从字典反序列化 RunContext"""
        shared_context = data.get("shared_context")
        if shared_context is not None and shared_context_cls is not None:
            if hasattr(shared_context_cls, "__ak_deserialize__"):
                shared_context = shared_context_cls.__ak_deserialize__(shared_context)
            elif hasattr(shared_context_cls, "from_dict"):
                shared_context = shared_context_cls.from_dict(shared_context)

        return cls(
            input=data.get("input", ""),
            shared_context=shared_context,
            user_id=data.get("user_id"),
            session_id=data.get("session_id", str(uuid4())),
            messages=data.get("messages", []),
            state=data.get("state", {}),
            branch=data.get("branch"),
            suspensions=[SuspensionRecord(**s) for s in data.get("suspensions", [])],
            resume_idempotency=data.get("resume_idempotency", {}),
        )

    def to_json(self) -> str:
        """将 RunContext 序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, shared_context_cls: Optional[Any] = None) -> "RunContext":
        """从 JSON 字符串反序列化 RunContext"""
        return cls.from_dict(json.loads(json_str), shared_context_cls)
