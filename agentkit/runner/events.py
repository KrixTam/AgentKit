"""
agentkit/runner/events.py — Event / RunResult

运行过程中产生的事件及最终结果。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Event:
    """运行过程中产生的事件"""
    agent: str                          # 产生事件的 Agent 名称
    type: str                           # 事件类型
    data: Any = None
    timestamp: float = field(default_factory=time.time)

    # 事件类型:
    #   llm_response, tool_call, tool_result, handoff,
    #   final_output, escalate, callback, error, permission_denied


@dataclass
class RunResult:
    """运行最终结果"""
    final_output: Any = None
    events: list[Event] = field(default_factory=list)
    last_agent: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and self.final_output is not None
