"""
agentkit/runner/events.py — Event / RunResult

运行过程中产生的事件及最终结果。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Type, TypeVar, Dict

T = TypeVar("T")

class EventType(str, Enum):
    """标准事件类型枚举（继承 str 以保持兼容性）"""
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    HANDOFF = "handoff"
    FINAL_OUTPUT = "final_output"
    ESCALATE = "escalate"
    CALLBACK = "callback"
    ERROR = "error"
    PERMISSION_DENIED = "permission_denied"
    
    # 新增生命周期与控制流事件
    ON_LOAD = "on_load"
    ON_UNLOAD = "on_unload"
    LOOP_ITERATION = "loop_iteration"
    LOOP_EXHAUSTED = "loop_exhausted"
    THOUGHT = "thought"
    
    # 新增挂起/恢复事件
    SUSPEND_REQUESTED = "suspend_requested"
    HUMAN_INPUT_RECEIVED = "human_input_received"

@dataclass
class Event:
    """运行过程中产生的事件"""
    agent: str                          # 产生事件的 Agent 名称
    type: str                           # 事件类型 (建议使用 EventType，但也兼容任意字符串)
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    
    # 链路追踪字段
    trace_path: Optional[str] = None
    parent_agent: Optional[str] = None

    def validate_data(self, schema: Type[T]) -> T:
        """
        强类型校验 Event.data。
        如果 data 是一个字典，则尝试将其转换为传入的 schema (Pydantic BaseModel 或 dataclass)。
        校验失败将抛出 ValueError，并给出可定位的错误信息。
        """
        if self.data is None:
            raise ValueError(f"Event data is None, expected {schema.__name__}")
        
        # 兼容 Pydantic v1 / v2 和 dataclasses
        if hasattr(schema, "model_validate"):
            # Pydantic v2
            try:
                return schema.model_validate(self.data)
            except Exception as e:
                raise ValueError(f"Schema validation failed for event type '{self.type}': {e}")
        elif hasattr(schema, "parse_obj"):
            # Pydantic v1
            try:
                return schema.parse_obj(self.data)
            except Exception as e:
                raise ValueError(f"Schema validation failed for event type '{self.type}': {e}")
        else:
            # 尝试直接解包实例化（如普通类或 dataclass）
            try:
                if isinstance(self.data, dict):
                    return schema(**self.data)
                return schema(self.data)
            except Exception as e:
                raise ValueError(f"Instantiation failed for event type '{self.type}': {e}")

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "agent": self.agent,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "trace_path": self.trace_path,
            "parent_agent": self.parent_agent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """从字典反序列化"""
        return cls(
            agent=data.get("agent", ""),
            type=data.get("type", "unknown"),
            data=data.get("data"),
            timestamp=data.get("timestamp", time.time()),
            trace_path=data.get("trace_path"),
            parent_agent=data.get("parent_agent"),
        )



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
