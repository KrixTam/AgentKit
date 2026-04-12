"""
agentkit/llm/adapters/openai_adapter.py — OpenAI GPT 系列适配器

支持模型：gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o3, o4 等
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from ..base import BaseLLM
from ..types import (
    FinishReason,
    LLMConfig,
    LLMResponse,
    Message,
    MessageRole,
    StreamChunk,
    ToolCall,
    ToolDefinition,
    Usage,
)


class OpenAIAdapter(BaseLLM):
    """OpenAI GPT 系列适配器"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("请安装 openai: pip install 'agentkit[openai]'")
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.api_base,
            timeout=config.timeout,
        )

    async def generate(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        output_schema: type | None = None,
    ) -> LLMResponse:
        openai_messages = [self._convert_message(m) for m in messages]

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": openai_messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            **self.config.extra_params,
        }
        if self.config.max_tokens:
            kwargs["max_tokens"] = self.config.max_tokens
        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if output_schema:
            kwargs["response_format"] = self._build_response_format(output_schema)

        response = await self._client.chat.completions.create(**kwargs)
        return self._parse_response(response)

    async def generate_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        openai_messages = [self._convert_message(m) for m in messages]

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": openai_messages,
            "temperature": self.config.temperature,
            "stream": True,
            **self.config.extra_params,
        }
        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]

        stream = await self._client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish = chunk.choices[0].finish_reason
            yield StreamChunk(
                delta_content=delta.content if delta.content else None,
                finish_reason=self._map_finish_reason(finish) if finish else None,
            )

    # ------------------------------------------------------------------
    # 内部转换
    # ------------------------------------------------------------------

    def _convert_message(self, msg: Message) -> dict:
        result: dict[str, Any] = {"role": msg.role.value}

        if msg.role == MessageRole.TOOL:
            result["content"] = msg.content or ""
            result["tool_call_id"] = msg.tool_call_id
        elif msg.role == MessageRole.ASSISTANT and msg.tool_calls:
            result["content"] = msg.content
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments_json(),
                    },
                }
                for tc in msg.tool_calls
            ]
        else:
            result["content"] = msg.content or ""

        return result

    def _parse_response(self, response: Any) -> LLMResponse:
        choice = response.choices[0]
        message = choice.message

        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=self._map_finish_reason(choice.finish_reason),
            usage=self._parse_usage(response.usage),
            model=response.model,
            _raw=response,
        )

    @staticmethod
    def _map_finish_reason(reason: str | None) -> FinishReason:
        mapping = {
            "stop": FinishReason.STOP,
            "tool_calls": FinishReason.TOOL_CALLS,
            "length": FinishReason.LENGTH,
        }
        return mapping.get(reason or "", FinishReason.STOP)

    @staticmethod
    def _parse_usage(usage: Any) -> Usage:
        if not usage:
            return Usage()
        return Usage(
            prompt_tokens=usage.prompt_tokens or 0,
            completion_tokens=usage.completion_tokens or 0,
        )

    @staticmethod
    def _build_response_format(schema_class: type) -> dict:
        json_schema = schema_class.model_json_schema()  # type: ignore
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema_class.__name__,
                "schema": json_schema,
                "strict": True,
            },
        }

    def supports_structured_output(self) -> bool:
        return "gpt-4o" in self.config.model or "o1" in self.config.model
