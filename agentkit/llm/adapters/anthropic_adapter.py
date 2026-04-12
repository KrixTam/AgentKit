"""
agentkit/llm/adapters/anthropic_adapter.py — Anthropic Claude 系列适配器

差异最大的适配器：
1. system 消息单独传，不在 messages 中
2. tool_use 返回在 content 块中，不在独立字段
3. tool_result 通过 user 消息中的 content 块传递
4. 参数直接是 dict，不是 JSON 字符串
"""
from __future__ import annotations

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


class AnthropicAdapter(BaseLLM):
    """Anthropic Claude 系列适配器"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("请安装 anthropic: pip install 'agentkit[anthropic]'")
        self._client = AsyncAnthropic(
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
        system_prompt, anthropic_messages = self._split_system_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "max_tokens": self.config.max_tokens or 4096,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            **self.config.extra_params,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = [t.to_anthropic_format() for t in tools]
        if tool_choice:
            kwargs["tool_choice"] = self._map_tool_choice(tool_choice)

        response = await self._client.messages.create(**kwargs)
        return self._parse_response(response)

    async def generate_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        system_prompt, anthropic_messages = self._split_system_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "max_tokens": self.config.max_tokens or 4096,
            **self.config.extra_params,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = [t.to_anthropic_format() for t in tools]

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                chunk = self._parse_stream_event(event)
                if chunk:
                    yield chunk

    # ------------------------------------------------------------------
    # 内部转换
    # ------------------------------------------------------------------

    def _split_system_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        system_parts: list[str] = []
        other: list[dict] = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_parts.append(msg.content or "")
            else:
                other.append(self._convert_message(msg))
        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, other

    def _convert_message(self, msg: Message) -> dict:
        if msg.role == MessageRole.ASSISTANT:
            content: list[dict] = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,  # Anthropic 用 dict
                })
            return {"role": "assistant", "content": content}

        if msg.role == MessageRole.TOOL:
            return {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content or "",
                }],
            }

        return {"role": msg.role.value, "content": msg.content or ""}

    def _parse_response(self, response: Any) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))

        content = "\n".join(text_parts) if text_parts else None
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=self._map_stop_reason(response.stop_reason),
            usage=Usage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
            ),
            model=response.model,
            _raw=response,
        )

    @staticmethod
    def _map_stop_reason(reason: str | None) -> FinishReason:
        mapping = {
            "end_turn": FinishReason.STOP,
            "tool_use": FinishReason.TOOL_CALLS,
            "max_tokens": FinishReason.LENGTH,
        }
        return mapping.get(reason or "", FinishReason.STOP)

    @staticmethod
    def _map_tool_choice(choice: str) -> dict:
        if choice == "auto":
            return {"type": "auto"}
        if choice == "required":
            return {"type": "any"}
        if choice == "none":
            return {"type": "none"}
        return {"type": "tool", "name": choice}

    @staticmethod
    def _parse_stream_event(event: Any) -> StreamChunk | None:
        if hasattr(event, "type"):
            if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                return StreamChunk(delta_content=event.delta.text)
            if event.type == "message_delta" and hasattr(event.delta, "stop_reason") and event.delta.stop_reason:
                return StreamChunk(
                    finish_reason=AnthropicAdapter._map_stop_reason(event.delta.stop_reason)
                )
        return None

    def supports_structured_output(self) -> bool:
        return True
