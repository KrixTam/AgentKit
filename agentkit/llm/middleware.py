"""
agentkit/llm/middleware.py — LLM 中间件（重试 / 降级 / 成本追踪）
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator

from .base import BaseLLM
from .types import (
    LLMConfig,
    LLMResponse,
    Message,
    StreamChunk,
    ToolDefinition,
    Usage,
)

logger = logging.getLogger("agentkit.llm")


class RetryMiddleware(BaseLLM):
    """重试 + 降级中间件：包装 BaseLLM，失败自动重试 + 降级"""

    def __init__(self, inner: BaseLLM, config: LLMConfig | None = None):
        super().__init__(config or inner.config)
        self._inner = inner

    async def generate(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        output_schema: type | None = None,
    ) -> LLMResponse:
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                return await self._inner.generate(
                    messages, tools=tools, tool_choice=tool_choice, output_schema=output_schema
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM 调用失败 (尝试 %d/%d): %s - %s",
                    attempt + 1, self.config.max_retries, self._inner.model_name, e,
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))

        # 降级
        for fallback_model in self.config.fallback_models:
            try:
                logger.info("降级到备选模型: %s", fallback_model)
                from .registry import LLMRegistry
                fallback_llm = LLMRegistry.create(fallback_model)
                return await fallback_llm.generate(
                    messages, tools=tools, tool_choice=tool_choice, output_schema=output_schema
                )
            except Exception as e:
                logger.warning("备选模型 %s 也失败: %s", fallback_model, e)

        raise last_error  # type: ignore[misc]

    async def generate_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        for attempt in range(self.config.max_retries):
            try:
                async for chunk in self._inner.generate_stream(messages, tools=tools, tool_choice=tool_choice):
                    yield chunk
                return
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay * (2**attempt))


class CostTracker:
    """成本追踪器——记录每次 LLM 调用的 token 用量和费用"""

    PRICING: dict[str, dict[str, float]] = {
        "gpt-4o":            {"input": 2.50,  "output": 10.00},
        "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
        "claude-opus-4-20250514":   {"input": 15.00, "output": 75.00},
        "claude-sonnet-4-20250514": {"input": 3.00,  "output": 15.00},
        "gemini-2.5-pro":    {"input": 1.25,  "output": 10.00},
        "gemini-2.5-flash":  {"input": 0.15,  "output": 0.60},
        "deepseek-chat":     {"input": 0.14,  "output": 0.28},
    }

    def __init__(self) -> None:
        self.total_usage = Usage()
        self.total_cost_usd: float = 0.0
        self.call_count: int = 0
        self._records: list[dict[str, Any]] = []

    def record(self, model: str, usage: Usage) -> None:
        self.call_count += 1
        self.total_usage.prompt_tokens += usage.prompt_tokens
        self.total_usage.completion_tokens += usage.completion_tokens
        cost = self._calculate_cost(model, usage)
        self.total_cost_usd += cost
        self._records.append({
            "model": model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cost_usd": cost,
            "timestamp": time.time(),
        })

    def _calculate_cost(self, model: str, usage: Usage) -> float:
        pricing = self.PRICING.get(model)
        if not pricing:
            return 0.0
        return (usage.prompt_tokens / 1_000_000) * pricing["input"] + \
               (usage.completion_tokens / 1_000_000) * pricing["output"]

    def summary(self) -> dict[str, Any]:
        return {
            "total_calls": self.call_count,
            "total_tokens": self.total_usage.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "breakdown": self._records,
        }
