# LLM 统一适配层 — 自研方案详细设计

> 放弃 LiteLLM，完全自研多模型适配层  
> **设计目标**：屏蔽各 LLM 厂商的 API 差异，提供统一的调用接口，支持 Agent 级和 Skill 级的 LLM 配置  
> **日期**：2026-04-09

---

## 目录

- [一、各厂商 API 差异全景图](#一各厂商-api-差异全景图)
- [二、适配层架构设计](#二适配层架构设计)
- [三、统一类型系统](#三统一类型系统)
- [四、BaseLLM 抽象接口](#四basellm-抽象接口)
- [五、OpenAI 适配器实现](#五openai-适配器实现)
- [六、Anthropic 适配器实现](#六anthropic-适配器实现)
- [七、Google Gemini 适配器实现](#七google-gemini-适配器实现)
- [八、OpenAI 兼容厂商适配器](#八openai-兼容厂商适配器)
- [九、LLMRegistry 模型注册中心](#九llmregistry-模型注册中心)
- [十、高级功能：重试、降级、成本追踪](#十高级功能重试降级成本追踪)
- [十一、与 Agent / Skill 的集成方式](#十一与-agent--skill-的集成方式)
- [十二、项目结构](#十二项目结构)

---

## 一、各厂商 API 差异全景图

经过详细调研，以下是各主要 LLM 厂商在**工具调用（Function Calling）**方面的 API 差异：

### 1.1 工具定义格式对比

| 维度 | OpenAI | Anthropic (Claude) | Google (Gemini) |
|------|--------|--------------------|--------------------|
| **工具定义位置** | 请求体 `tools` 字段 | 请求体 `tools` 字段 | `GenerateContentConfig.tools` |
| **工具类型标记** | `type: "function"` | `type: "custom"` 或直接定义 | `function_declarations` 数组 |
| **参数格式** | JSON Schema | JSON Schema（`input_schema`） | JSON Schema（`parameters`） |
| **工具名称字段** | `function.name` | `name` | `name` |
| **工具描述字段** | `function.description` | `description` | `description` |

### 1.2 工具调用响应格式对比

| 维度 | OpenAI | Anthropic (Claude) | Google (Gemini) |
|------|--------|--------------------|--------------------|
| **停止原因** | `finish_reason: "tool_calls"` | `stop_reason: "tool_use"` | 响应中含 `function_call` part |
| **调用数据位置** | `message.tool_calls[]` | `content[].type == "tool_use"` | `parts[].function_call` |
| **调用 ID** | `tool_calls[].id` | `content[].id` | `function_call.id`（Gemini 3+） |
| **函数名** | `tool_calls[].function.name` | `content[].name` | `function_call.name` |
| **参数** | `tool_calls[].function.arguments`（JSON 字符串） | `content[].input`（dict 对象） | `function_call.args`（dict 对象） |

### 1.3 工具结果回传格式对比

| 维度 | OpenAI | Anthropic (Claude) | Google (Gemini) |
|------|--------|--------------------|--------------------|
| **角色** | `role: "tool"` | `role: "user"`（包含 tool_result） | `role: "user"`（包含 function_response） |
| **关联 ID** | `tool_call_id` | `tool_use_id` | `id`（Gemini 3）或按顺序匹配 |
| **结果内容** | `content`（字符串） | `content[]`（content block 数组） | `response`（dict） |

### 1.4 国内厂商情况

| 厂商 | API 兼容性 | 说明 |
|------|-----------|------|
| **通义千问** | ✅ 兼容 OpenAI 格式 | 百炼平台提供 OpenAI Chat Completion 兼容接口 |
| **智谱 (GLM)** | ✅ 兼容 OpenAI 格式 | 官方 SDK 兼容 OpenAI 格式 |
| **DeepSeek** | ✅ 兼容 OpenAI 格式 | API 完全兼容 OpenAI |
| **Moonshot (Kimi)** | ✅ 兼容 OpenAI 格式 | API 兼容 OpenAI |
| **百川** | ✅ 兼容 OpenAI 格式 | API 兼容 OpenAI |

**结论**：国内主流厂商几乎全部兼容 OpenAI 格式，只需一个 **OpenAI 兼容适配器**（调整 `api_base` 和 `api_key`）即可覆盖。

### 1.5 差异汇总：我们需要适配什么

```
┌─────────────────────────────────────────────────────────────────┐
│                  需要独立实现的适配器（3 个）                      │
│                                                                 │
│  ① OpenAIAdapter        — OpenAI 原生 API                      │
│  ② AnthropicAdapter     — Anthropic 原生 API（差异最大）        │
│  ③ GoogleAdapter        — Google Gemini 原生 API               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                  可复用 OpenAI 适配器的厂商                       │
│                                                                 │
│  通义千问 / 智谱 / DeepSeek / Moonshot / 百川 / Azure OpenAI    │
│  → 只需修改 api_base + api_key，格式完全兼容                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、适配层架构设计

```
┌──────────────────────────────────────────────────────────────────┐
│                     Agent / Skill（上层调用方）                    │
│                                                                  │
│  agent.model = "gpt-4o"                                          │
│  skill.llm_config = {"model": "claude-sonnet-4-20250514", ...}              │
│         │                                                        │
│  ┌──────▼──────────────────────────────────────────────────┐     │
│  │               LLMRegistry（模型注册中心）                │     │
│  │                                                         │     │
│  │  • 根据 model 标识自动选择适配器                         │     │
│  │  • 管理全局默认配置                                      │     │
│  │  • 支持注册自定义适配器                                  │     │
│  └──────┬──────────────────────────────────────────────────┘     │
│         │                                                        │
│  ┌──────▼──────────────────────────────────────────────────┐     │
│  │               BaseLLM（统一抽象接口）                    │     │
│  │                                                         │     │
│  │  • generate()      — 标准调用                           │     │
│  │  • generate_stream() — 流式调用                         │     │
│  │  • 使用统一的消息/工具/响应类型                          │     │
│  └──────┬───────────┬───────────┬──────────────────────────┘     │
│         │           │           │                                │
│  ┌──────▼────┐ ┌────▼─────┐ ┌──▼──────────┐ ┌───────────────┐   │
│  │  OpenAI   │ │Anthropic │ │   Google    │ │ OpenAI 兼容   │   │
│  │  Adapter  │ │ Adapter  │ │  Adapter    │ │   Adapter     │   │
│  │           │ │          │ │             │ │               │   │
│  │ openai    │ │anthropic │ │ google-genai│ │ openai SDK    │   │
│  │ SDK       │ │ SDK      │ │ SDK         │ │ + 自定义 base │   │
│  └─────┬─────┘ └────┬─────┘ └──────┬─────┘ └───────┬───────┘   │
│        │            │              │               │            │
│  ┌─────▼────┐ ┌─────▼─────┐ ┌─────▼──────┐ ┌─────▼──────────┐ │
│  │ OpenAI   │ │ Anthropic │ │  Google    │ │ 通义/智谱/     │ │
│  │ API      │ │ API       │ │  API       │ │ DeepSeek/...   │ │
│  └──────────┘ └───────────┘ └────────────┘ └────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 三、统一类型系统

这是整个适配层的基石——**框架内部只使用这套统一类型，各适配器负责与厂商格式的双向转换**。

```python
"""
llm/types.py — LLM 统一类型系统
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any, Union
from enum import Enum
import json


# ============================================================
# 消息类型
# ============================================================

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """LLM 返回的工具调用请求"""
    id: str                     # 调用 ID（用于关联结果）
    name: str                   # 工具名称
    arguments: dict[str, Any]   # 工具参数（已解析为 dict）

    def arguments_json(self) -> str:
        """参数序列化为 JSON 字符串"""
        return json.dumps(self.arguments, ensure_ascii=False)


@dataclass
class Message:
    """统一消息格式"""
    role: MessageRole
    content: Optional[str] = None
    
    # 仅 role=assistant 时可能出现
    tool_calls: list[ToolCall] = field(default_factory=list)
    
    # 仅 role=tool 时使用
    tool_call_id: Optional[str] = None   # 关联的 ToolCall.id
    
    # 原始数据（调试用，各适配器可存放厂商原始格式）
    _raw: Any = field(default=None, repr=False)


# ============================================================
# 工具定义
# ============================================================

@dataclass
class ToolDefinition:
    """统一工具定义格式"""
    name: str                              # 工具名称
    description: str                       # 工具描述（给 LLM 看的）
    parameters: dict[str, Any]             # 参数 JSON Schema
    strict: bool = False                   # 是否启用严格模式（OpenAI/Anthropic）
    
    def to_openai_format(self) -> dict:
        """转为 OpenAI 格式"""
        tool = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
        if self.strict:
            tool["function"]["strict"] = True
        return tool
    
    def to_anthropic_format(self) -> dict:
        """转为 Anthropic 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }
    
    def to_google_format(self) -> dict:
        """转为 Google Gemini 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ============================================================
# LLM 响应
# ============================================================

class FinishReason(str, Enum):
    STOP = "stop"                # 正常结束（有文本输出）
    TOOL_CALLS = "tool_calls"    # 需要执行工具
    LENGTH = "length"            # 达到 max_tokens 截断
    ERROR = "error"              # 出错


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
    content: Optional[str] = None                    # 文本回复
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: FinishReason = FinishReason.STOP
    usage: Usage = field(default_factory=Usage)
    model: str = ""                                  # 实际使用的模型标识
    
    # 原始响应（调试用）
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
    delta_content: Optional[str] = None    # 增量文本
    delta_tool_call: Optional[ToolCall] = None  # 增量工具调用
    finish_reason: Optional[FinishReason] = None
    usage: Optional[Usage] = None


# ============================================================
# LLM 配置
# ============================================================

@dataclass
class LLMConfig:
    """LLM 调用配置"""
    model: str                                            # 模型标识
    api_key: Optional[str] = None                         # API Key
    api_base: Optional[str] = None                        # 自定义 API 端点
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    timeout: int = 60                                     # 超时（秒）
    max_retries: int = 3                                  # 最大重试次数
    retry_delay: float = 1.0                              # 重试间隔（秒）
    fallback_models: list[str] = field(default_factory=list)  # 降级模型列表
    extra_params: dict[str, Any] = field(default_factory=dict)  # 厂商特有参数
    
    def with_overrides(self, **kwargs) -> "LLMConfig":
        """创建带覆盖参数的新配置（用于 Skill 级覆盖）"""
        from dataclasses import asdict
        base = asdict(self)
        base.update(kwargs)
        return LLMConfig(**base)
```

---

## 四、BaseLLM 抽象接口

```python
"""
llm/base.py — LLM 抽象基类
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from .types import (
    LLMConfig, Message, ToolDefinition, LLMResponse, StreamChunk
)


class BaseLLM(ABC):
    """
    LLM 统一抽象接口。
    
    所有适配器必须实现此接口。上层代码（Agent/Runner）只依赖这个接口，
    不直接接触任何厂商 SDK。
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,       # "auto" / "required" / "none" / 具体工具名
        output_schema: type | None = None,     # 结构化输出
    ) -> LLMResponse:
        """
        标准调用：发送消息，返回完整响应。
        
        Args:
            messages: 对话消息列表
            tools: 可用工具定义
            tool_choice: 工具选择策略
            output_schema: 结构化输出的 Pydantic 模型类
        
        Returns:
            LLMResponse: 统一格式的响应
        """
        ...
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        流式调用：发送消息，逐块返回响应。
        """
        ...
    
    def supports_tool_calling(self) -> bool:
        """当前模型是否支持工具调用"""
        return True  # 子类可覆盖
    
    def supports_structured_output(self) -> bool:
        """当前模型是否支持结构化输出"""
        return False  # 子类可覆盖
    
    @property
    def model_name(self) -> str:
        return self.config.model
```

---

## 五、OpenAI 适配器实现

```python
"""
llm/adapters/openai_adapter.py — OpenAI 适配器
"""
import json
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI

from ..base import BaseLLM
from ..types import (
    LLMConfig, Message, MessageRole, ToolDefinition,
    LLMResponse, ToolCall, FinishReason, Usage, StreamChunk
)


class OpenAIAdapter(BaseLLM):
    """
    OpenAI GPT 系列适配器。
    
    支持模型：gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o3, 等
    """
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.api_key,        # None → 从环境变量 OPENAI_API_KEY 读取
            base_url=config.api_base,      # None → 使用默认
            timeout=config.timeout,
        )
    
    async def generate(self, messages, *, tools=None, tool_choice=None, output_schema=None):
        # 1. 转换消息格式
        openai_messages = [self._convert_message(m) for m in messages]
        
        # 2. 构建请求参数
        kwargs = {
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
        
        # 3. 调用 API
        response = await self._client.chat.completions.create(**kwargs)
        
        # 4. 解析响应
        return self._parse_response(response)
    
    async def generate_stream(self, messages, *, tools=None, tool_choice=None):
        openai_messages = [self._convert_message(m) for m in messages]
        
        kwargs = {
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
                usage=self._parse_usage(chunk.usage) if hasattr(chunk, 'usage') and chunk.usage else None,
            )
    
    # ===== 内部转换方法 =====
    
    def _convert_message(self, msg: Message) -> dict:
        """框架消息 → OpenAI 消息"""
        result = {"role": msg.role.value}
        
        if msg.role == MessageRole.TOOL:
            result["content"] = msg.content or ""
            result["tool_call_id"] = msg.tool_call_id
        elif msg.role == MessageRole.ASSISTANT and msg.tool_calls:
            result["content"] = msg.content  # 可以是 None
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments_json(),
                    }
                }
                for tc in msg.tool_calls
            ]
        else:
            result["content"] = msg.content or ""
        
        return result
    
    def _parse_response(self, response) -> LLMResponse:
        """OpenAI 响应 → 框架响应"""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=self._map_finish_reason(choice.finish_reason),
            usage=self._parse_usage(response.usage),
            model=response.model,
            _raw=response,
        )
    
    def _map_finish_reason(self, reason) -> FinishReason:
        mapping = {
            "stop": FinishReason.STOP,
            "tool_calls": FinishReason.TOOL_CALLS,
            "length": FinishReason.LENGTH,
        }
        return mapping.get(reason, FinishReason.STOP)
    
    def _parse_usage(self, usage) -> Usage:
        if not usage:
            return Usage()
        return Usage(
            prompt_tokens=usage.prompt_tokens or 0,
            completion_tokens=usage.completion_tokens or 0,
        )
    
    def _build_response_format(self, schema_class):
        """构建结构化输出的 response_format"""
        json_schema = schema_class.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema_class.__name__,
                "schema": json_schema,
                "strict": True,
            }
        }
    
    def supports_structured_output(self) -> bool:
        return "gpt-4o" in self.config.model or "o1" in self.config.model
```

---

## 六、Anthropic 适配器实现

```python
"""
llm/adapters/anthropic_adapter.py — Anthropic Claude 适配器

注意：Anthropic 的 API 格式与 OpenAI 差异最大：
1. system 消息单独传，不在 messages 中
2. tool_use 返回在 content 块中，不在独立字段
3. tool_result 通过 user 消息中的 content 块传递
4. 参数直接是 dict，不是 JSON 字符串
"""
import json
from typing import AsyncGenerator
from anthropic import AsyncAnthropic

from ..base import BaseLLM
from ..types import (
    LLMConfig, Message, MessageRole, ToolDefinition,
    LLMResponse, ToolCall, FinishReason, Usage, StreamChunk
)


class AnthropicAdapter(BaseLLM):
    """
    Anthropic Claude 系列适配器。
    
    支持模型：claude-opus-4-20250514, claude-sonnet-4-20250514, claude-haiku, 等
    """
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = AsyncAnthropic(
            api_key=config.api_key,        # None → 从 ANTHROPIC_API_KEY 读取
            base_url=config.api_base,
            timeout=config.timeout,
        )
    
    async def generate(self, messages, *, tools=None, tool_choice=None, output_schema=None):
        # 1. 提取 system 消息（Anthropic 要求 system 单独传）
        system_prompt, anthropic_messages = self._split_system_messages(messages)
        
        # 2. 构建请求参数
        kwargs = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "max_tokens": self.config.max_tokens or 4096,   # Anthropic 必须指定
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
        
        # 3. 调用 API
        response = await self._client.messages.create(**kwargs)
        
        # 4. 解析响应
        return self._parse_response(response)
    
    async def generate_stream(self, messages, *, tools=None, tool_choice=None):
        system_prompt, anthropic_messages = self._split_system_messages(messages)
        
        kwargs = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "max_tokens": self.config.max_tokens or 4096,
            "stream": True,
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
    
    # ===== 内部转换方法 =====
    
    def _split_system_messages(self, messages: list[Message]):
        """
        分离 system 消息。
        Anthropic 要求 system 单独传，不能放在 messages 中。
        """
        system_parts = []
        other_messages = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_parts.append(msg.content or "")
            else:
                other_messages.append(self._convert_message(msg))
        
        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, other_messages
    
    def _convert_message(self, msg: Message) -> dict:
        """框架消息 → Anthropic 消息"""
        
        if msg.role == MessageRole.ASSISTANT:
            content = []
            # 文本内容
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            # 工具调用
            for tc in msg.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,      # ⚠️ Anthropic 用 dict，不是 JSON 字符串
                })
            return {"role": "assistant", "content": content}
        
        elif msg.role == MessageRole.TOOL:
            # ⚠️ Anthropic 的 tool_result 放在 user 消息的 content 块中
            return {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,     # ⚠️ 字段名不同
                    "content": msg.content or "",
                }]
            }
        
        else:  # user
            return {"role": msg.role.value, "content": msg.content or ""}
    
    def _parse_response(self, response) -> LLMResponse:
        """Anthropic 响应 → 框架响应"""
        text_parts = []
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,     # 已经是 dict
                ))
        
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
    
    def _map_stop_reason(self, reason) -> FinishReason:
        mapping = {
            "end_turn": FinishReason.STOP,
            "tool_use": FinishReason.TOOL_CALLS,
            "max_tokens": FinishReason.LENGTH,
        }
        return mapping.get(reason, FinishReason.STOP)
    
    def _map_tool_choice(self, choice: str) -> dict:
        if choice == "auto":
            return {"type": "auto"}
        elif choice == "required":
            return {"type": "any"}
        elif choice == "none":
            return {"type": "none"}          # Anthropic 不设置 tools 即可
        else:
            return {"type": "tool", "name": choice}
    
    def _parse_stream_event(self, event) -> StreamChunk | None:
        """解析流式事件"""
        if hasattr(event, 'type'):
            if event.type == 'content_block_delta':
                if hasattr(event.delta, 'text'):
                    return StreamChunk(delta_content=event.delta.text)
            elif event.type == 'message_delta':
                if event.delta.stop_reason:
                    return StreamChunk(
                        finish_reason=self._map_stop_reason(event.delta.stop_reason)
                    )
        return None
    
    def supports_structured_output(self) -> bool:
        return True   # Claude 支持通过 tool_use 实现结构化输出
```

---

## 七、Google Gemini 适配器实现

```python
"""
llm/adapters/google_adapter.py — Google Gemini 适配器

注意：Gemini 的 API 结构与 OpenAI/Anthropic 差异显著：
1. 使用 google.genai SDK，不是 REST 直接调用
2. 工具定义通过 types.Tool(function_declarations=[...]) 传入
3. 工具调用结果通过 Part.from_function_response() 传入
4. 参数直接是 dict，不是 JSON 字符串
"""
from typing import AsyncGenerator, Optional
from google import genai
from google.genai import types as genai_types

from ..base import BaseLLM
from ..types import (
    LLMConfig, Message, MessageRole, ToolDefinition,
    LLMResponse, ToolCall, FinishReason, Usage, StreamChunk
)


class GoogleAdapter(BaseLLM):
    """
    Google Gemini 系列适配器。
    
    支持模型：gemini-2.5-pro, gemini-2.5-flash, gemini-3-flash, 等
    """
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = genai.Client(api_key=config.api_key)
    
    async def generate(self, messages, *, tools=None, tool_choice=None, output_schema=None):
        # 1. 转换消息
        system_instruction, contents = self._convert_messages(messages)
        
        # 2. 构建配置
        gen_config = genai_types.GenerateContentConfig(
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_output_tokens=self.config.max_tokens,
            **self.config.extra_params,
        )
        
        # 3. 工具
        if tools:
            gen_config.tools = [genai_types.Tool(
                function_declarations=[self._convert_tool(t) for t in tools]
            )]
        
        if system_instruction:
            gen_config.system_instruction = system_instruction
        
        # 4. 调用 API
        response = await self._client.aio.models.generate_content(
            model=self.config.model,
            contents=contents,
            config=gen_config,
        )
        
        # 5. 解析响应
        return self._parse_response(response)
    
    async def generate_stream(self, messages, *, tools=None, tool_choice=None):
        system_instruction, contents = self._convert_messages(messages)
        
        gen_config = genai_types.GenerateContentConfig(
            temperature=self.config.temperature,
        )
        if tools:
            gen_config.tools = [genai_types.Tool(
                function_declarations=[self._convert_tool(t) for t in tools]
            )]
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
    
    # ===== 内部转换方法 =====
    
    def _convert_messages(self, messages: list[Message]):
        """
        框架消息 → Gemini 格式。
        Gemini 的 system 通过 system_instruction 传，
        messages 只有 "user" 和 "model" 两种角色。
        """
        system_parts = []
        contents = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_parts.append(msg.content or "")
            
            elif msg.role == MessageRole.USER:
                contents.append(genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=msg.content or "")],
                ))
            
            elif msg.role == MessageRole.ASSISTANT:
                parts = []
                if msg.content:
                    parts.append(genai_types.Part.from_text(text=msg.content))
                for tc in msg.tool_calls:
                    parts.append(genai_types.Part(
                        function_call=genai_types.FunctionCall(
                            name=tc.name,
                            args=tc.arguments,
                            id=tc.id,
                        )
                    ))
                contents.append(genai_types.Content(role="model", parts=parts))
            
            elif msg.role == MessageRole.TOOL:
                # ⚠️ Gemini 的工具结果通过 user 角色 + Part.from_function_response 传递
                contents.append(genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_function_response(
                        name="",   # Gemini 3+ 通过 id 匹配
                        response={"result": msg.content},
                        id=msg.tool_call_id,
                    )],
                ))
        
        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, contents
    
    def _convert_tool(self, tool: ToolDefinition) -> dict:
        """框架工具 → Gemini 函数声明"""
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
    
    def _parse_response(self, response) -> LLMResponse:
        """Gemini 响应 → 框架响应"""
        candidate = response.candidates[0]
        
        text_parts = []
        tool_calls = []
        
        for part in candidate.content.parts:
            if part.text:
                text_parts.append(part.text)
            elif part.function_call:
                fc = part.function_call
                tool_calls.append(ToolCall(
                    id=getattr(fc, 'id', f"call_{fc.name}"),
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
    
    def _parse_stream_chunk(self, chunk) -> StreamChunk | None:
        if chunk.candidates and chunk.candidates[0].content.parts:
            part = chunk.candidates[0].content.parts[0]
            if part.text:
                return StreamChunk(delta_content=part.text)
        return None
    
    def supports_structured_output(self) -> bool:
        return "gemini-2" in self.config.model or "gemini-3" in self.config.model
```

---

## 八、OpenAI 兼容厂商适配器

**这是最巧妙的部分**——国内大部分厂商都兼容 OpenAI 格式，所以只需继承 `OpenAIAdapter`，改一下 `api_base` 和 `api_key` 即可。

```python
"""
llm/adapters/openai_compatible.py — OpenAI 兼容厂商适配器

覆盖：通义千问、智谱 GLM、DeepSeek、Moonshot、百川、Azure OpenAI 等
"""
from .openai_adapter import OpenAIAdapter
from ..types import LLMConfig


class OpenAICompatibleAdapter(OpenAIAdapter):
    """
    OpenAI 兼容厂商的通用适配器。
    
    原理：这些厂商的 API 格式完全兼容 OpenAI，
    只需要替换 api_base 和 api_key 即可。
    """
    pass  # 直接复用 OpenAIAdapter 的全部逻辑


# ===== 预置的厂商配置 =====

# 各厂商的默认 API 端点
PROVIDER_ENDPOINTS = {
    "deepseek":   "https://api.deepseek.com/v1",
    "qwen":       "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu":      "https://open.bigmodel.cn/api/paas/v4",
    "moonshot":   "https://api.moonshot.cn/v1",
    "baichuan":   "https://api.baichuan-ai.com/v1",
    "azure":      None,  # Azure 需要用户自行配置
}

# 各厂商的 API Key 环境变量名
PROVIDER_ENV_KEYS = {
    "deepseek":   "DEEPSEEK_API_KEY",
    "qwen":       "DASHSCOPE_API_KEY",
    "zhipu":      "ZHIPU_API_KEY",
    "moonshot":   "MOONSHOT_API_KEY",
    "baichuan":   "BAICHUAN_API_KEY",
    "azure":      "AZURE_OPENAI_API_KEY",
}
```

---

## 九、LLMRegistry 模型注册中心

```python
"""
llm/registry.py — 模型注册中心
"""
import os
from typing import Optional
from .base import BaseLLM
from .types import LLMConfig
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.anthropic_adapter import AnthropicAdapter
from .adapters.google_adapter import GoogleAdapter
from .adapters.openai_compatible import (
    OpenAICompatibleAdapter, PROVIDER_ENDPOINTS, PROVIDER_ENV_KEYS
)


class LLMRegistry:
    """
    模型注册中心。
    
    职责：
    1. 根据模型标识自动选择适配器
    2. 管理全局默认配置
    3. 支持注册自定义适配器
    
    模型标识规则：
    - "gpt-4o"          → OpenAIAdapter
    - "claude-sonnet-4-20250514"  → AnthropicAdapter
    - "gemini-2.5-pro"  → GoogleAdapter
    - "deepseek/deepseek-chat" → OpenAICompatibleAdapter (DeepSeek)
    - "qwen/qwen-max"   → OpenAICompatibleAdapter (通义千问)
    - "zhipu/glm-4"     → OpenAICompatibleAdapter (智谱)
    """
    
    # 全局默认配置
    _default_model: str = "gpt-4o"
    _default_config: Optional[LLMConfig] = None
    
    # 自定义适配器注册表
    _custom_adapters: dict[str, type[BaseLLM]] = {}
    
    # 模型前缀 → 适配器类型的映射
    _PREFIX_MAP: dict[str, type[BaseLLM]] = {
        # OpenAI 原生
        "gpt-":      OpenAIAdapter,
        "o1":        OpenAIAdapter,
        "o3":        OpenAIAdapter,
        "o4":        OpenAIAdapter,
        
        # Anthropic 原生
        "claude-":   AnthropicAdapter,
        
        # Google 原生
        "gemini-":   GoogleAdapter,
        
        # 国内厂商（OpenAI 兼容）
        "deepseek/": OpenAICompatibleAdapter,
        "qwen/":     OpenAICompatibleAdapter,
        "zhipu/":    OpenAICompatibleAdapter,
        "moonshot/": OpenAICompatibleAdapter,
        "baichuan/": OpenAICompatibleAdapter,
        "azure/":    OpenAICompatibleAdapter,
    }
    
    @classmethod
    def set_default(cls, model: str, **kwargs):
        """设置全局默认模型"""
        cls._default_model = model
        cls._default_config = LLMConfig(model=model, **kwargs)
    
    @classmethod
    def register(cls, prefix: str, adapter_class: type[BaseLLM]):
        """注册自定义适配器"""
        cls._custom_adapters[prefix] = adapter_class
    
    @classmethod
    def create(cls, model_or_config) -> BaseLLM:
        """
        创建 LLM 实例。
        
        Args:
            model_or_config: 可以是：
                - str: 模型标识（如 "gpt-4o"）
                - LLMConfig: 完整配置
                - BaseLLM: 直接返回
        """
        # 已经是 LLM 实例
        if isinstance(model_or_config, BaseLLM):
            return model_or_config
        
        # 构建配置
        if isinstance(model_or_config, str):
            config = cls._build_config_from_string(model_or_config)
        elif isinstance(model_or_config, LLMConfig):
            config = model_or_config
        else:
            raise ValueError(f"不支持的参数类型: {type(model_or_config)}")
        
        # 查找适配器
        adapter_class = cls._resolve_adapter(config.model)
        
        return adapter_class(config)
    
    @classmethod
    def create_default(cls) -> BaseLLM:
        """创建全局默认 LLM"""
        if cls._default_config:
            return cls.create(cls._default_config)
        return cls.create(cls._default_model)
    
    @classmethod
    def _resolve_adapter(cls, model: str) -> type[BaseLLM]:
        """根据模型标识解析适配器类型"""
        # 1. 先查自定义注册
        for prefix, adapter_cls in cls._custom_adapters.items():
            if model.startswith(prefix):
                return adapter_cls
        
        # 2. 再查内置映射
        for prefix, adapter_cls in cls._PREFIX_MAP.items():
            if model.startswith(prefix):
                return adapter_cls
        
        # 3. 默认走 OpenAI 兼容
        return OpenAICompatibleAdapter
    
    @classmethod
    def _build_config_from_string(cls, model_str: str) -> LLMConfig:
        """
        从模型标识字符串构建配置。
        
        处理 "provider/model" 格式：
        - "deepseek/deepseek-chat" → api_base=DeepSeek, model=deepseek-chat
        - "qwen/qwen-max" → api_base=通义千问, model=qwen-max
        """
        config_kwargs = {"model": model_str}
        
        if "/" in model_str:
            provider, actual_model = model_str.split("/", 1)
            
            # 设置 api_base
            if provider in PROVIDER_ENDPOINTS and PROVIDER_ENDPOINTS[provider]:
                config_kwargs["api_base"] = PROVIDER_ENDPOINTS[provider]
            
            # 设置 api_key（从环境变量）
            if provider in PROVIDER_ENV_KEYS:
                env_key = PROVIDER_ENV_KEYS[provider]
                api_key = os.environ.get(env_key)
                if api_key:
                    config_kwargs["api_key"] = api_key
            
            # 实际模型名不含 provider 前缀
            config_kwargs["model"] = actual_model
        
        return LLMConfig(**config_kwargs)
```

---

## 十、高级功能：重试、降级、成本追踪

```python
"""
llm/middleware.py — LLM 中间件（重试、降级、日志、成本追踪）
"""
import asyncio
import time
import logging
from typing import AsyncGenerator
from .base import BaseLLM
from .types import LLMConfig, Message, ToolDefinition, LLMResponse, StreamChunk, Usage

logger = logging.getLogger("llm")


class RetryMiddleware(BaseLLM):
    """
    重试 + 降级中间件。
    包装一个 BaseLLM，在调用失败时自动重试，并在所有重试失败后降级到备选模型。
    """
    
    def __init__(self, inner: BaseLLM, config: LLMConfig):
        super().__init__(config)
        self._inner = inner
    
    async def generate(self, messages, **kwargs) -> LLMResponse:
        last_error = None
        
        # 重试主模型
        for attempt in range(self.config.max_retries):
            try:
                return await self._inner.generate(messages, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM 调用失败 (尝试 {attempt+1}/{self.config.max_retries}): "
                    f"{self._inner.model_name} - {e}"
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))  # 指数退避
        
        # 降级到备选模型
        for fallback_model in self.config.fallback_models:
            try:
                logger.info(f"降级到备选模型: {fallback_model}")
                from .registry import LLMRegistry
                fallback_llm = LLMRegistry.create(fallback_model)
                return await fallback_llm.generate(messages, **kwargs)
            except Exception as e:
                logger.warning(f"备选模型 {fallback_model} 也失败: {e}")
                continue
        
        raise last_error
    
    async def generate_stream(self, messages, **kwargs) -> AsyncGenerator[StreamChunk, None]:
        # 流式调用的重试逻辑（简化版，只重试不降级）
        for attempt in range(self.config.max_retries):
            try:
                async for chunk in self._inner.generate_stream(messages, **kwargs):
                    yield chunk
                return
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))


class CostTracker:
    """
    成本追踪器。
    记录每次 LLM 调用的 token 用量和费用。
    """
    
    # 各模型的单价（每 1M token）
    PRICING = {
        "gpt-4o":           {"input": 2.50,   "output": 10.00},
        "gpt-4o-mini":      {"input": 0.15,   "output": 0.60},
        "claude-opus-4-20250514":  {"input": 15.00,  "output": 75.00},
        "claude-sonnet-4-20250514":{"input": 3.00,   "output": 15.00},
        "gemini-2.5-pro":   {"input": 1.25,   "output": 10.00},
        "gemini-2.5-flash": {"input": 0.15,   "output": 0.60},
        "deepseek-chat":    {"input": 0.14,   "output": 0.28},
    }
    
    def __init__(self):
        self.total_usage = Usage()
        self.total_cost_usd: float = 0.0
        self.call_count: int = 0
        self._records: list[dict] = []
    
    def record(self, model: str, usage: Usage):
        """记录一次调用"""
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
        input_cost = (usage.prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def summary(self) -> dict:
        return {
            "total_calls": self.call_count,
            "total_tokens": self.total_usage.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "breakdown": self._records,
        }
```

---

## 十一、与 Agent / Skill 的集成方式

### Agent 级 LLM 配置

```python
# 方式一：字符串标识（最简单）
agent = Agent(
    name="assistant",
    model="gpt-4o",                       # → 自动创建 OpenAIAdapter
)

# 方式二：LLMConfig（精细控制）
agent = Agent(
    name="assistant",
    model=LLMConfig(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=4096,
        fallback_models=["gpt-4o-mini"],   # 降级到 mini
    ),
)

# 方式三：直接传 BaseLLM 实例（完全自定义）
custom_llm = OpenAIAdapter(LLMConfig(model="gpt-4o", api_base="https://my-proxy.com/v1"))
agent = Agent(
    name="assistant",
    model=custom_llm,
)

# 方式四：国内厂商
agent = Agent(
    name="assistant",
    model="deepseek/deepseek-chat",        # → 自动创建 OpenAICompatibleAdapter
)
```

### Skill 级 LLM 配置

```yaml
# SKILL.md
---
name: code-review
description: 代码审查技能
metadata:
  llm_config:
    model: "claude-sonnet-4-20250514"    # Skill 专用 Claude（更擅长代码）
    temperature: 0.2
    max_tokens: 8192
---
```

### 完整调用链

```
Agent(model="gpt-4o") 启动
  │
  ├─ 正常对话 → LLMRegistry.create("gpt-4o") → OpenAIAdapter
  │
  ├─ 激活 code-review Skill → 检测 llm_config
  │   └─ LLMRegistry.create("claude-sonnet-4-20250514") → AnthropicAdapter
  │       └─ Skill 相关的 LLM 调用走 Claude
  │
  ├─ Skill 执行完毕 → 恢复 gpt-4o
  │
  └─ gpt-4o 调用失败 → RetryMiddleware 重试 3 次
      └─ 全部失败 → 降级到 gpt-4o-mini
```

---

## 十二、项目结构

```
llm/
├── __init__.py                    # 公开 API
│   # from .types import LLMConfig, Message, ToolDefinition, LLMResponse, ...
│   # from .base import BaseLLM
│   # from .registry import LLMRegistry
│
├── types.py                       # 统一类型系统（Message, ToolCall, LLMResponse, ...）
├── base.py                        # BaseLLM 抽象接口
├── registry.py                    # LLMRegistry 模型注册中心
├── middleware.py                  # RetryMiddleware, CostTracker
│
├── adapters/                      # 各厂商适配器
│   ├── __init__.py
│   ├── openai_adapter.py          # OpenAI GPT 系列
│   ├── anthropic_adapter.py       # Anthropic Claude 系列
│   ├── google_adapter.py          # Google Gemini 系列
│   └── openai_compatible.py       # OpenAI 兼容厂商（DeepSeek/通义/智谱/...）
│
└── utils/
    ├── schema.py                  # Python 函数签名 → JSON Schema 转换
    └── token_counter.py           # Token 计数估算
```

### 依赖的第三方库

```
# 核心（至少安装一个）
openai>=1.0.0          # OpenAI + 国内兼容厂商
anthropic>=0.30.0      # Anthropic Claude
google-genai>=1.0.0    # Google Gemini

# 可选
pydantic>=2.0          # 类型校验和 JSON Schema
```

---

> **设计完毕。** 这套自研适配层：  
> - 用 **3 个核心适配器 + 1 个兼容适配器** 覆盖了市面上几乎所有主流 LLM  
> - 通过统一的 `BaseLLM` 接口，上层（Agent/Skill/Runner）完全不感知厂商差异  
> - 通过 `LLMRegistry` 的前缀匹配，实现了零配置的模型自动路由  
> - 支持重试、降级、成本追踪等生产级需求  
> - 项目结构清晰，每个文件职责单一  
