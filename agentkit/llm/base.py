"""
agentkit/llm/base.py — LLM 抽象基类

所有适配器必须实现此接口。上层代码（Agent / Runner）只依赖这个接口，
不直接接触任何厂商 SDK。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator

from .types import LLMConfig, LLMResponse, Message, StreamChunk, ToolDefinition


class BaseLLM(ABC):
    """LLM 统一抽象接口"""

    def __init__(self, config: LLMConfig):
        self.config = config

    # ------------------------------------------------------------------
    # 核心方法（子类必须实现）
    # ------------------------------------------------------------------

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        output_schema: type | None = None,
    ) -> LLMResponse:
        """标准调用：发送消息，返回完整响应"""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式调用：发送消息，逐块返回响应"""
        ...
        # 确保是 async generator
        yield  # type: ignore  # pragma: no cover

    # ------------------------------------------------------------------
    # 能力查询（子类可覆盖）
    # ------------------------------------------------------------------

    def supports_tool_calling(self) -> bool:
        return True

    def supports_structured_output(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # 便捷属性
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        return self.config.model
