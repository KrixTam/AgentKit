"""
agentkit/llm/types.py — LLM 统一类型系统

框架内部只使用这套统一类型，各适配器负责与厂商格式的双向转换。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ============================================================
# 消息角色
# ============================================================

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# ============================================================
# 工具调用
# ============================================================

@dataclass
class ToolCall:
    """LLM 返回的工具调用请求"""
    id: str                       # 调用 ID（用于关联结果）
    name: str                     # 工具名称
    arguments: dict[str, Any]     # 工具参数（已解析为 dict）

    def arguments_json(self) -> str:
        """参数序列化为 JSON 字符串（OpenAI 格式需要）"""
        return json.dumps(self.arguments, ensure_ascii=False)


# ============================================================
# 统一消息
# ============================================================

@dataclass
class Message:
    """统一消息格式"""
    role: MessageRole
    content: Optional[str] = None

    # 仅 role=ASSISTANT 时可能出现
    tool_calls: list[ToolCall] = field(default_factory=list)

    # 仅 role=TOOL 时使用，关联 ToolCall.id
    tool_call_id: Optional[str] = None

    # 原始数据（调试用，各适配器可存放厂商原始格式）
    _raw: Any = field(default=None, repr=False)

    @staticmethod
    def system(content: str) -> "Message":
        return Message(role=MessageRole.SYSTEM, content=content)

    @staticmethod
    def user(content: str) -> "Message":
        return Message(role=MessageRole.USER, content=content)

    @staticmethod
    def assistant(content: Optional[str] = None, tool_calls: list[ToolCall] | None = None) -> "Message":
        return Message(role=MessageRole.ASSISTANT, content=content, tool_calls=tool_calls or [])

    @staticmethod
    def tool(tool_call_id: str, content: str) -> "Message":
        return Message(role=MessageRole.TOOL, content=content, tool_call_id=tool_call_id)


# ============================================================
# 工具定义
# ============================================================

@dataclass
class ToolDefinition:
    """统一工具定义格式"""
    name: str
    description: str
    parameters: dict[str, Any]   # JSON Schema
    strict: bool = False

    def to_openai_format(self) -> dict:
        tool: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
        if self.strict:
            tool["function"]["strict"] = True
        return tool

    def to_anthropic_format(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_google_format(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ============================================================
# LLM 响应
# ============================================================

class FinishReason(str, Enum):
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    ERROR = "error"


@dataclass
class Usage:
    """Token 使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    """统一响应格式"""
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: FinishReason = FinishReason.STOP
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    _raw: Any = field(default=None, repr=False)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def has_content(self) -> bool:
        return self.content is not None and self.content.strip() != ""


@dataclass
class StreamChunk:
    """流式输出的单个块"""
    delta_content: Optional[str] = None
    delta_tool_call: Optional[ToolCall] = None
    finish_reason: Optional[FinishReason] = None
    usage: Optional[Usage] = None


# ============================================================
# LLM 配置
# ============================================================

@dataclass
class LLMConfig:
    """LLM 调用配置"""
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    fallback_models: list[str] = field(default_factory=list)
    extra_params: dict[str, Any] = field(default_factory=dict)

    def with_overrides(self, **kwargs: Any) -> "LLMConfig":
        """创建带覆盖参数的新配置"""
        from dataclasses import asdict
        base = asdict(self)
        base.update(kwargs)
        return LLMConfig(**base)
