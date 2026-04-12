"""
agentkit/llm/adapters/google_adapter.py — Google Gemini 系列适配器

差异点：
1. 使用 google.genai SDK
2. assistant 角色映射为 "model"
3. 工具调用结果通过 Part.from_function_response() 传入
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


class GoogleAdapter(BaseLLM):
    """Google Gemini 系列适配器"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from google import genai
        except ImportError:
            raise ImportError("请安装 google-genai: pip install 'agentkit[google]'")
        self._client = genai.Client(api_key=config.api_key)
        self._genai_types = __import__("google.genai.types", fromlist=["types"])

    async def generate(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        output_schema: type | None = None,
    ) -> LLMResponse:
        types = self._genai_types
        system_instruction, contents = self._convert_messages(messages)

        config_kwargs: dict[str, Any] = {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            **self.config.extra_params,
        }
        if self.config.max_tokens:
            config_kwargs["max_output_tokens"] = self.config.max_tokens

        gen_config = types.GenerateContentConfig(**config_kwargs)

        if tools:
            gen_config.tools = [
                types.Tool(function_declarations=[t.to_google_format() for t in tools])
            ]
        if system_instruction:
            gen_config.system_instruction = system_instruction

        response = await self._client.aio.models.generate_content(
            model=self.config.model,
            contents=contents,
            config=gen_config,
        )
        return self._parse_response(response)

    async def generate_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        types = self._genai_types
        system_instruction, contents = self._convert_messages(messages)

        gen_config = types.GenerateContentConfig(temperature=self.config.temperature)
        if tools:
            gen_config.tools = [
                types.Tool(function_declarations=[t.to_google_format() for t in tools])
            ]
        if system_instruction:
            gen_config.system_instruction = system_instruction

        async for chunk in self._client.aio.models.generate_content_stream(
            model=self.config.model,
            contents=contents,
            config=gen_config,
        ):
            parsed = self._parse_stream_chunk(chunk)
            if parsed:
                yield parsed

    # ------------------------------------------------------------------
    # 内部转换
    # ------------------------------------------------------------------

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list]:
        types = self._genai_types
        system_parts: list[str] = []
        contents: list = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_parts.append(msg.content or "")
            elif msg.role == MessageRole.USER:
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.content or "")],
                ))
            elif msg.role == MessageRole.ASSISTANT:
                parts = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                for tc in msg.tool_calls:
                    parts.append(types.Part(
                        function_call=types.FunctionCall(name=tc.name, args=tc.arguments, id=tc.id)
                    ))
                contents.append(types.Content(role="model", parts=parts))
            elif msg.role == MessageRole.TOOL:
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name="",
                        response={"result": msg.content},
                        id=msg.tool_call_id,
                    )],
                ))

        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, contents

    def _parse_response(self, response: Any) -> LLMResponse:
        candidate = response.candidates[0]
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for part in candidate.content.parts:
            if part.text:
                text_parts.append(part.text)
            elif part.function_call:
                fc = part.function_call
                tool_calls.append(ToolCall(
                    id=getattr(fc, "id", f"call_{fc.name}"),
                    name=fc.name,
                    arguments=dict(fc.args) if fc.args else {},
                ))

        content = "\n".join(text_parts) if text_parts else None
        finish_reason = FinishReason.TOOL_CALLS if tool_calls else FinishReason.STOP

        usage = Usage()
        if response.usage_metadata:
            usage = Usage(
                prompt_tokens=response.usage_metadata.prompt_token_count or 0,
                completion_tokens=response.usage_metadata.candidates_token_count or 0,
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            model=self.config.model,
            _raw=response,
        )

    @staticmethod
    def _parse_stream_chunk(chunk: Any) -> StreamChunk | None:
        if chunk.candidates and chunk.candidates[0].content.parts:
            part = chunk.candidates[0].content.parts[0]
            if part.text:
                return StreamChunk(delta_content=part.text)
        return None

    def supports_structured_output(self) -> bool:
        return "gemini-2" in self.config.model or "gemini-3" in self.config.model
