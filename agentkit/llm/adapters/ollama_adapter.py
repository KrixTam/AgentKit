"""
agentkit/llm/adapters/ollama_adapter.py — Ollama 本地模型适配器

使用 Ollama 原生 /api/chat 接口（非 OpenAI 兼容接口），因为：
1. 原生 API 响应更快
2. 原生支持 function calling（tool_calls）
3. 直接获取最终 content

默认非流式调用（与 OpenAI/Google ADK 一致），流式由 generate_stream() 提供。
默认开启 thinking 模式。

支持模型：所有 Ollama 本地模型（如 qwen3.5:cloud, qwen3.5:4b, llama3, gemma 等）
"""
from __future__ import annotations

import json
import logging
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

logger = logging.getLogger("agentkit.llm.ollama")

# Ollama 默认端点
DEFAULT_OLLAMA_BASE = "http://localhost:11434"


class OllamaAdapter(BaseLLM):
    """Ollama 本地模型适配器（使用原生 /api/chat 接口）"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._base_url = (config.api_base or DEFAULT_OLLAMA_BASE).rstrip("/")
        # Ollama 本地模型推理可能较慢（尤其 thinking 模式），自动放宽超时
        if self.config.timeout <= 60:
            self.config.timeout = 300

    @property
    def _think_enabled(self) -> bool:
        """是否启用 thinking（深度思考）模式，默认开启。"""
        return self.config.extra_params.get("think", True)

    def _inject_no_think(self, messages: list[Message]) -> list[Message]:
        """当 think=False 时，在 system prompt 末尾追加 /no_think 标记。"""
        if self._think_enabled:
            return messages

        result: list[Message] = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM and msg.content:
                result.append(Message(
                    role=msg.role,
                    content=msg.content + "\n\n/no_think",
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                ))
            else:
                result.append(msg)
        return result

    def _build_payload(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        output_schema: type | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """构建 Ollama /api/chat 请求体"""
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [self._convert_message(m) for m in messages],
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
            },
        }
        if self.config.max_tokens:
            payload["options"]["num_predict"] = self.config.max_tokens
        if tools:
            payload["tools"] = [self._convert_tool(t) for t in tools]
        if output_schema:
            payload["format"] = output_schema.model_json_schema()
        return payload

    # ------------------------------------------------------------------
    # 核心调用方法
    # ------------------------------------------------------------------

    async def generate(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        output_schema: type | None = None,
    ) -> LLMResponse:
        """非流式调用（默认）——一次请求返回完整结果"""
        import aiohttp

        messages = self._inject_no_think(messages)
        payload = self._build_payload(messages, tools=tools, output_schema=output_schema, stream=False)
        url = f"{self._base_url}/api/chat"
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=timeout) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Ollama API 错误 ({resp.status}): {text}")
                data = await resp.json()

        return self._parse_response(data)

    async def generate_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式调用——逐 token 返回，适合实时展示"""
        import aiohttp

        messages = self._inject_no_think(messages)
        payload = self._build_payload(messages, tools=tools, stream=True)
        url = f"{self._base_url}/api/chat"
        # 流式模式下 sock_read 设大（等待第一个 token 可能需要较长时间）
        timeout = aiohttp.ClientTimeout(total=None, sock_read=self.config.timeout)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=timeout) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Ollama API 错误 ({resp.status}): {text}")

                async for line in resp.content:
                    line_text = line.decode("utf-8").strip()
                    if not line_text:
                        continue
                    try:
                        chunk_data = json.loads(line_text)
                    except json.JSONDecodeError:
                        continue

                    msg = chunk_data.get("message", {})
                    content = msg.get("content", "")
                    done = chunk_data.get("done", False)

                    if content:
                        yield StreamChunk(delta_content=content)
                    if done:
                        yield StreamChunk(finish_reason=FinishReason.STOP)

    # ------------------------------------------------------------------
    # 内部转换
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_message(msg: Message) -> dict:
        """框架消息 → Ollama 消息"""
        result: dict[str, Any] = {"role": msg.role.value, "content": msg.content or ""}

        if msg.role == MessageRole.ASSISTANT and msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,  # Ollama 接受 dict
                    },
                }
                for tc in msg.tool_calls
            ]

        if msg.role == MessageRole.TOOL:
            result["role"] = "tool"
            result["content"] = msg.content or ""

        return result

    @staticmethod
    def _convert_tool(tool: ToolDefinition) -> dict:
        """框架工具定义 → Ollama 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    @staticmethod
    def _parse_response(data: dict) -> LLMResponse:
        """Ollama 响应 → 框架响应"""
        msg = data.get("message", {})
        content = msg.get("content", "") or ""
        raw_tool_calls = msg.get("tool_calls", [])

        tool_calls: list[ToolCall] = []
        for tc in raw_tool_calls:
            func_data = tc.get("function", {})
            tool_calls.append(ToolCall(
                id=tc.get("id", f"call_{func_data.get('name', 'unknown')}"),
                name=func_data.get("name", ""),
                arguments=func_data.get("arguments", {}),
            ))

        # 判断结束原因
        if tool_calls:
            finish_reason = FinishReason.TOOL_CALLS
        elif data.get("done", False):
            finish_reason = FinishReason.STOP
        else:
            finish_reason = FinishReason.LENGTH

        # 解析 token 用量
        usage = Usage(
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )

        return LLMResponse(
            content=content.strip() if content else None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            model=data.get("model", ""),
            _raw=data,
        )

    def supports_tool_calling(self) -> bool:
        # Ollama 支持部分模型的 tool calling
        return True

    def supports_structured_output(self) -> bool:
        return True  # Ollama 支持 format 参数
