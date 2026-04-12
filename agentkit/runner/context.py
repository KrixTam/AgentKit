"""
agentkit/runner/context.py — RunContext（一次运行的完整上下文）
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4


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
