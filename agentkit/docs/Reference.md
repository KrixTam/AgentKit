# AgentKit API 参考手册

> 本文档覆盖 AgentKit 所有公共 API 的完整参数说明和用法示例。

---

## 目录

- [Agent 类](#agent-类)
  - [Agent](#agent)
  - [BaseAgent](#baseagent)
  - [SequentialAgent / ParallelAgent / LoopAgent](#编排-agent)
- [Runner 类](#runner-类)
  - [Runner](#runner)
  - [RunContext](#runcontext)
  - [ContextStore](#contextstore)
  - [RunResult](#runresult)
  - [Event 与 EventType](#event-与-eventtype)
- [Tool 类](#tool-类)
  - [function_tool 装饰器](#function_tool-装饰器)
  - [FunctionTool](#functiontool)
  - [BaseTool / BaseToolset](#basetool--basetoolset)
  - [StructuredDataTool (结构化数据源)](#structureddatatool-结构化数据源)
- [Skill 类](#skill-类)
  - [Skill](#skill)
  - [SkillFrontmatter](#skillfrontmatter)
  - [load_skill_from_dir](#load_skill_from_dir)
  - [SkillRegistry](#skillregistry)
- [LLM 类](#llm-类)
  - [LLMRegistry](#llmregistry)
  - [LLMConfig](#llmconfig)
  - [BaseLLM](#basellm)
  - [Message / ToolCall / LLMResponse](#消息与响应类型)
- [安全类](#安全类)
  - [InputGuardrail / OutputGuardrail](#guardrail)
  - [PermissionPolicy](#permissionpolicy)
- [记忆类](#记忆类)
  - [BaseMemoryProvider / Memory](#basememoryprovider)

---

## Agent 类

### Agent

核心 LLM Agent，开发者最常使用的类。

```python
from agentkit import Agent
```

**构造参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str` | **必填** | Agent 名称 |
| `description` | `str` | `""` | 描述（Handoff 和发现时使用） |
| `model` | `str \| LLMConfig \| BaseLLM` | `""` | 模型标识。空字符串表示向上继承父 Agent 的模型 |
| `instructions` | `str \| Callable` | `""` | 系统提示词。可以是字符串或动态函数 `(ctx, agent) -> str` |
| `tools` | `list` | `[]` | 工具列表，接受 `BaseTool`、`BaseToolset` 或普通 `Callable` |
| `skills` | `list[Skill]` | `[]` | Skill 列表 |
| `handoffs` | `list[Agent]` | `[]` | Handoff 目标 Agent 列表 |
| `output_type` | `type \| None` | `None` | 结构化输出类型（Pydantic 模型） |
| `input_guardrails` | `list[InputGuardrail]` | `[]` | 输入安全护栏 |
| `output_guardrails` | `list[OutputGuardrail]` | `[]` | 输出安全护栏 |
| `permission_policy` | `PermissionPolicy \| None` | `None` | 工具权限策略 |
| `memory` | `BaseMemoryProvider \| None` | `None` | 记忆提供者 |
| `tool_use_behavior` | `str` | `"run_llm_again"` | 工具调用后行为：`"run_llm_again"` 或 `"stop"` |
| `max_tool_rounds` | `int` | `20` | 单次运行最大工具调用轮次 |
| `enable_cache` | `bool` | `True` | LLM 响应缓存，默认开启。对相同输入直接返回缓存结果，缓存绑定 Agent 实例生命周期。仅缓存纯文本回复，不缓存工具调用响应 |
| `cache_ttl` | `int` | `300` | 缓存有效期（秒）。过期条目自动淘汰 |
| `memory_async_write` | `bool` | `True` | 记忆写入模式。`True`=fire-and-forget 异步写入（不阻塞返回）；`False`=同步等待写入完成（多轮串行对话推荐） |
| `model_cosplay_enabled` | `bool` | `False` | 是否开启 ModelCosplay。关闭时如果类已预设 `model`，实例化时不允许覆盖；开启后允许实例化和运行时改写模型 |
| `before_agent_callback` | `Callable \| None` | `None` | Agent 运行前回调 |
| `after_agent_callback` | `Callable \| None` | `None` | Agent 运行后回调 |
| `before_model_callback` | `Callable \| None` | `None` | LLM 调用前回调（可拦截/改写） |
| `after_model_callback` | `Callable \| None` | `None` | LLM 调用后回调（可改写响应） |
| `before_tool_callback` | `Callable \| None` | `None` | 工具调用前回调（可拦截执行） |
| `after_tool_callback` | `Callable \| None` | `None` | 工具调用后回调（可改写工具结果） |
| `before_handoff_callback` | `Callable \| None` | `None` | Handoff 前回调（可改写目标 Agent） |
| `after_handoff_callback` | `Callable \| None` | `None` | Handoff 后回调 |
| `on_error_callback` | `Callable \| None` | `None` | 错误回调 |
| `fail_fast_on_hook_error` | `bool` | `False` | Hook 抛错时是否立即中断流程 |

**方法**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `as_tool` | `(name: str, description: str) -> FunctionTool` | 将自身包装为工具，供其他 Agent 调用 |
| `get_instructions` | `async (ctx) -> str` | 获取系统提示词（动态解析） |
| `get_all_tools` | `async (ctx) -> list[BaseTool]` | 汇总所有工具（tools + skills + handoffs） |
| `clear_cache` | `() -> None` | 清空当前 Agent 实例的 LLM 缓存 |
| `apply_model_cosplay` | `(model_override: Any) -> Agent` | 运行时改写当前实例 `model`（仅在 `model_cosplay_enabled=True` 时允许） |

**示例**：

```python
agent = Agent(
    name="assistant",
    instructions="你是一个中文助手",
    model="ollama/qwen3.5:cloud",
    tools=[my_tool],
    skills=[my_skill],
)
```

---

### BaseAgent

所有 Agent 的基类。开发者通常不直接使用，除非要实现自定义 Agent 类型。

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 名称 |
| `description` | `str` | 描述 |
| `sub_agents` | `list[BaseAgent]` | 子 Agent（自动建立父子关系） |
| `before_agent_callback` | `Callable \| None` | 运行前回调 |
| `after_agent_callback` | `Callable \| None` | 运行后回调 |
| `model_cosplay_enabled` | `bool` | 是否开启 ModelCosplay（默认 `False`） |

**子类化**：

```python
class MyAgent(BaseAgent):
    async def _run_impl(self, ctx):
        yield Event(agent=self.name, type="final_output", data="自定义输出")
```

---

### 编排 Agent

**SequentialAgent** — 按顺序执行子 Agent

```python
from agentkit import SequentialAgent
pipeline = SequentialAgent(name="pipeline", sub_agents=[agent_a, agent_b, agent_c])
```

**ParallelAgent** — 并行执行子 Agent（分支隔离）

```python
from agentkit import ParallelAgent
parallel = ParallelAgent(name="parallel", early_exit=True, sub_agents=[agent_a, agent_b])
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `early_exit` | `bool` | ParallelAgent 专属：是否在一个子分支升级（escalate）时立即取消其他分支，默认 False |

**LoopAgent** — 循环执行，直到 escalate 或满足退出条件

```python
from agentkit import LoopAgent
loop = LoopAgent(name="loop", max_iterations=5, loop_condition=my_condition, sub_agents=[coder, reviewer])
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `max_iterations` | `int` | LoopAgent 专属：最大循环次数，默认 10。达到上限时会发出 `loop_exhausted` 事件 |
| `loop_condition` | `Callable \| None` | LoopAgent 专属：每次循环前的判断函数 `(ctx, state) -> bool`，返回 `False` 终止循环 |

---

## Runner 类

### Runner

Agent 运行引擎。全部为类方法，无需实例化。

```python
from agentkit import Runner
```

**方法**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `run` | `async (agent, *, input, context=None, user_id=None, session_id=None, max_turns=10) -> RunResult` | 异步运行 |
| `run_sync` | `(agent, **kwargs) -> RunResult` | 同步运行（内部调用 asyncio.run） |
| `run_streamed` | `async (agent, *, input, user_id=None, session_id=None, **kwargs) -> AsyncGenerator[Event, None]` | 流式运行，实时产出 Event |
| `run_with_checkpoint` | `async (agent, *, input, session_id, context_store, ..., max_turns=10) -> AsyncGenerator[Event, None]` | 流式运行（支持挂起），遇到 `suspend_requested` 时自动保存上下文与执行指针（turn/current_agent/agent_path），并追加发出 `suspended` 事件 |
| `resume` | `async (agent, *, session_id, user_input, context_store, ..., suspension_id=None, idempotency_key=None) -> AsyncGenerator[Event, None]` | 恢复被挂起会话；优先按 checkpoint 的 `agent_path` 定位恢复节点，再按 `suspension_id`（或最新 pending）恢复挂起点；支持 `idempotency_key` 幂等 |

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `agent` | `Agent` | **必填** | 要运行的 Agent |
| `input` | `str` | **必填** | 用户输入 |
| `context` | `Any` | `None` | 共享上下文（传给 RunContext.shared_context） |
| `user_id` | `str \| None` | `None` | 用户 ID（用于记忆隔离） |
| `session_id` | `str \| None` | `None` | 会话 ID（不传则自动生成） |
| `max_turns` | `int` | `10` | 最大轮次（每个 turn 包含一次 LLM 调用） |

---

### RunContext

一次运行的完整上下文，承载了状态流转与持久化的核心职责。

```python
from agentkit.runner.context import RunContext
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `input` | `str` | 初始用户输入 |
| `shared_context` | `Any` | 自定义共享对象，支持 `__ak_serialize__` 魔法方法 |
| `user_id` | `str \| None` | 用户 ID（用于多租户和记忆隔离） |
| `session_id` | `str` | 会话 ID，默认随机生成（用于断点续跑和上下文隔离） |
| `messages` | `list[dict]` | 当前完整的对话消息链 |
| `state` | `dict` | 运行期间的内部状态（不再承载挂起协议字段） |
| `suspensions` | `list[SuspensionRecord]` | 框架托管的挂起记录列表（含 `suspension_id/tool_call_id/tool_name/prompt/form_schema/resume_strategy`） |
| `resume_idempotency` | `dict[str, dict]` | resume 幂等记录，避免重复提交人工输入 |

**方法**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `to_dict` | `() -> dict` | 序列化上下文状态（可调用 `shared_context.__ak_serialize__`） |
| `from_dict` | `(data: dict, shared_context_cls) -> RunContext` | 从字典反序列化 |
| `to_json` / `from_json` | 同上 | 将上下文与 JSON 字符串转换 |

---

### ContextStore

上下文存储协议，为 Runner 提供断点续跑支持。

```python
from agentkit.runner.context_store import ContextStore, InMemoryContextStore, FileContextStore
```

**方法**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `save` | `(session_id: str, context: RunContext) -> None` | 存储挂起的 RunContext 快照 |
| `load` | `(session_id: str, shared_context_cls=None) -> RunContext \| None` | 加载恢复 RunContext；不存在时返回 `None` |
| `delete` | `(session_id: str) -> None` | 清理会话状态 |

**内置实现**：
- `InMemoryContextStore`：将上下文存储在内存字典中。
- `FileContextStore(directory=".agentkit_checkpoints")`：以 JSON 文件落盘。

---

### RunResult

```python
from agentkit import RunResult
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `final_output` | `Any` | 最终输出内容 |
| `events` | `list[Event]` | 运行过程中的所有事件 |
| `last_agent` | `str \| None` | 最后执行的 Agent 名称 |
| `error` | `str \| None` | 错误信息 |
| `success` | `bool` | 是否成功（`error is None and final_output is not None`） |

---

### Event 与 EventType

```python
from agentkit import Event
from agentkit.runner.events import EventType
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `agent` | `str` | 产生事件的 Agent 名称 |
| `type` | `str` | 事件类型（推荐使用 `EventType` 枚举） |
| `data` | `Any` | 事件数据 |
| `timestamp` | `float` | 时间戳 |
| `trace_path` | `str \| None` | 事件产生时的调用链路路径 |
| `parent_agent` | `str \| None` | 产生事件的父 Agent |

**标准事件类型 (EventType)**：

| 枚举常量 | 字符串值 | 含义 |
|------|------|------|
| `EventType.LLM_RESPONSE` | `llm_response` | LLM 返回了响应 |
| `EventType.TOOL_CALL` | `tool_call` | 准备调用工具 |
| `EventType.TOOL_RESULT` | `tool_result` | 工具执行完成，data 包含 `{tool, result}` |
| `EventType.FINAL_OUTPUT` | `final_output` | 最终输出 |
| `EventType.HANDOFF` | `handoff` | Agent 交接，data 包含 `{target}` |
| `EventType.ESCALATE` | `escalate` | 上报/退出信号（LoopAgent 或 early_exit 用） |
| `EventType.ERROR` | `error` | 错误 |
| `EventType.CALLBACK` | `callback` | 回调产生的事件 |
| `EventType.PERMISSION_DENIED` | `permission_denied` | 权限拒绝 |
| `EventType.ON_LOAD` | `on_load` | 资源加载事件 |
| `EventType.ON_UNLOAD` | `on_unload` | 资源释放事件 |
| `EventType.LOOP_ITERATION` | `loop_iteration` | 循环单次迭代事件 |
| `EventType.LOOP_EXHAUSTED` | `loop_exhausted` | 循环耗尽事件 |
| `EventType.THOUGHT` | `thought` | Agent 内心思考 |
| `EventType.SUSPEND_REQUESTED` | `suspend_requested` | 任务挂起请求（HITL 核心事件） |
| `EventType.HUMAN_INPUT_RECEIVED` | `human_input_received` | 收到人工恢复输入 |

补充说明：`suspended` 为 Runner 在 checkpoint 挂起后追加的状态事件（字符串事件类型，非 `EventType` 枚举成员），用于平台侧状态机对齐。

**方法**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `validate_data` | `(schema: Type[T]) -> T` | 强类型校验 `data` 是否符合传入的 Pydantic 或 dataclass schema，失败抛出 ValueError |
| `to_dict` | `() -> dict` | 事件序列化 |
| `from_dict` | `(data: dict) -> Event` | 事件反序列化 |

---

## Tool 类

### function_tool 装饰器

```python
from agentkit import function_tool
```

将 Python 函数自动转换为 LLM 可调用的工具。

**用法 1：无参数**

```python
@function_tool
def my_tool(query: str, top_k: int = 5) -> str:
    """工具描述（自动从 docstring 提取）"""
    return "result"
```

**用法 2：带参数**

```python
@function_tool(name="custom_name", description="自定义描述", needs_approval=True, timeout=30)
async def my_tool(target: str) -> str:
    ...
```

**装饰器参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str \| None` | `None` | 自定义名称（默认取函数名） |
| `description` | `str \| None` | `None` | 自定义描述（默认取 docstring 首行） |
| `needs_approval` | `bool` | `False` | 是否需要人工审批 |
| `timeout` | `float \| None` | `None` | 超时秒数 |

**自动推断规则**：
- 工具名称 ← 函数名
- 工具描述 ← docstring 首行
- 参数 JSON Schema ← 函数签名的类型注解
- 如果第一个参数命名为 `ctx`/`context`/`tool_context`，自动识别为上下文参数

---

### FunctionTool

底层工具类，通常通过 `@function_tool` 创建，也可手动构造。

```python
from agentkit import FunctionTool

tool = FunctionTool(
    name="my_tool",
    description="工具描述",
    handler=my_function,
    json_schema={"type": "object", "properties": {...}},
)
```

**类方法**：

| 方法 | 说明 |
|------|------|
| `FunctionTool.from_function(func)` | 从普通 Python 函数自动创建 |

---

### request_human_input

在工具层触发中断，请求外部人工介入（HITL）的辅助函数。

```python
from agentkit.tools.base_tool import request_human_input

def my_sensitive_action():
    request_human_input("请确认是否执行此操作 (yes/no)")
```

该函数会抛出 `HumanInputRequested` 异常，被 Runner 捕获后转为 `EventType.SUSPEND_REQUESTED` 挂起任务。

---

### BaseTool / BaseToolset

**BaseTool**：工具抽象基类，自定义工具时继承。

```python
class MyTool(BaseTool):
    async def execute(self, ctx, arguments: dict) -> Any:
        ...
    def to_tool_definition(self) -> ToolDefinition:
        ...
```

**BaseToolset**：工具集基类，可动态展开为多个工具。

```python
class MyToolset(BaseToolset):
    async def get_tools(self, ctx) -> list[BaseTool]:
        ...
```

---

### StructuredDataTool (结构化数据源)

参数化数据查询工具基类，通过分离“参数抽取”与“SQL/GQL 组装”，从根本上避免 LLM 生成语句导致的注入攻击风险。

```python
from agentkit import StructuredDataTool, ResultFormatter
from agentkit.tools.sqlite_tool import SQLiteTool
from agentkit.tools.nebula_tool import NebulaGraphTool
```

**通用参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称 |
| `description` | `str` | 工具描述 |
| `parameters_schema` | `Type[BaseModel]` | Pydantic Schema，约束 LLM 输出的参数格式 |
| `query_template` | `str` | 底层查询语句模板 |
| `formatter` | `ResultFormatter \| None` | 结果格式化器，将数据库原生结果标准化 |

**内置实现**：

- **`SQLiteTool`**：关系型数据库工具。使用 `sqlite3` 的命名占位符机制绑定参数。
- **`NebulaGraphTool`**：图数据库工具。支持 `connection_pool` 生命周期管理，允许注入动态连接池。

---

## Skill 类

### Skill

```python
from agentkit import Skill, SkillFrontmatter, SkillResources
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `frontmatter` | `SkillFrontmatter` | L1：元数据（name + description） |
| `instructions` | `str` | L2：SKILL.md 正文指令 |
| `resources` | `SkillResources` | L3：附加资源 |
| `context` | `dict` | **运行期**：存放生命周期绑定的外部资源（连接池等） |
| `on_load_hook` | `Callable \| None` | **生命周期钩子**：在 Agent 执行前加载资源 |
| `on_unload_hook` | `Callable \| None` | **生命周期钩子**：在 Agent 执行后释放资源 |

**便捷属性**：`skill.name`、`skill.description`、`skill.additional_tools`、`skill.llm_config`

---

### SkillFrontmatter

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | kebab-case 标识符（≤64 字符） |
| `description` | `str` | 描述（≤1024 字符） |
| `license` | `str \| None` | 许可证 |
| `metadata` | `dict` | 扩展元数据，可含 `additional_tools` 和 `llm_config` |

---

### load_skill_from_dir

```python
from agentkit import load_skill_from_dir

skill = load_skill_from_dir("./skills/my-skill")
```

从目录加载 Skill。目录必须包含 `SKILL.md`，且目录名必须与 Skill 的 `name` 字段一致。

---

### SkillRegistry

```python
from agentkit import SkillRegistry

registry = SkillRegistry()
registry.add_search_path("./skills")
skills = registry.discover()           # 自动发现目录下所有 Skill
skill = registry.get("my-skill")       # 按名称获取
```

---

## LLM 类

### LLMRegistry

模型注册中心，根据模型标识前缀自动选择适配器。

```python
from agentkit import LLMRegistry
```

| 方法 | 说明 |
|------|------|
| `LLMRegistry.set_default(model, **kwargs)` | 设置全局默认模型 |
| `LLMRegistry.create(model_or_config)` | 创建 LLM 实例（自动路由） |
| `LLMRegistry.create_default()` | 创建默认模型实例 |
| `LLMRegistry.register(prefix, adapter_class)` | 注册自定义适配器 |

**前缀路由表**：

| 前缀 | 适配器 | 需要的包 |
|------|--------|---------|
| `gpt-`、`o1`、`o3`、`o4` | OpenAIAdapter | `openai` |
| `claude-` | AnthropicAdapter | `anthropic` |
| `gemini-` | GoogleAdapter | `google-genai` |
| `ollama/` | OllamaAdapter | `aiohttp` |
| `deepseek/`、`qwen/`、`zhipu/`、`moonshot/`、`baichuan/`、`azure/` | OpenAICompatibleAdapter | `openai` |

---

### LLMConfig

LLM 调用的精细配置。

```python
from agentkit import LLMConfig

config = LLMConfig(
    model="gpt-4o",
    temperature=0.3,
    max_tokens=4096,
    fallback_models=["gpt-4o-mini"],
)
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | `str` | **必填** | 模型标识 |
| `api_key` | `str \| None` | `None` | API Key（None 则从环境变量读取） |
| `api_base` | `str \| None` | `None` | 自定义 API 端点 |
| `temperature` | `float` | `0.7` | 温度 |
| `max_tokens` | `int \| None` | `None` | 最大 token 数 |
| `top_p` | `float` | `1.0` | top_p |
| `timeout` | `int` | `60` | 超时秒数 |
| `max_retries` | `int` | `3` | 最大重试次数 |
| `retry_delay` | `float` | `1.0` | 重试间隔（秒） |
| `fallback_models` | `list[str]` | `[]` | 降级模型列表 |
| `extra_params` | `dict` | `{}` | 厂商特有参数（见下方说明） |

**`extra_params` 常用参数**：

| 参数 | 适用适配器 | 默认值 | 说明 |
|------|-----------|--------|------|
| `think` | OllamaAdapter | `True` | 是否启用 thinking（深度思考）模式。默认开启。设为 `False` 可关闭深度推理，纯对话场景可能加速 2-3 倍，但工具调用场景下 cloud 模型关闭后可能反而更慢，请按实际测试结果选择 |

```python
from agentkit.llm.registry import LLMRegistry

# 默认开启 thinking
llm = LLMRegistry.create("ollama/qwen3.5:cloud")

# 需要关闭时（纯对话场景可能更快）
llm = LLMRegistry.create("ollama/qwen3.5:cloud")
llm.config.extra_params["think"] = False
```

---

### BaseLLM

LLM 抽象接口，自定义适配器时继承。

```python
class MyLLM(BaseLLM):
    async def generate(self, messages, *, tools=None, tool_choice=None, output_schema=None):
        ...
    async def generate_stream(self, messages, *, tools=None, tool_choice=None):
        ...
```

---

### 消息与响应类型

**Message** — 统一消息格式

```python
from agentkit import Message

Message.system("你是助手")
Message.user("你好")
Message.assistant("你好！")
Message.tool(tool_call_id="call_123", content="工具结果")
```

**ToolCall** — LLM 返回的工具调用

```python
from agentkit import ToolCall
tc = ToolCall(id="call_123", name="get_weather", arguments={"city": "北京"})
```

**LLMResponse** — 统一响应

| 属性 | 类型 | 说明 |
|------|------|------|
| `content` | `str \| None` | 文本回复 |
| `tool_calls` | `list[ToolCall]` | 工具调用请求 |
| `finish_reason` | `FinishReason` | `STOP` / `TOOL_CALLS` / `LENGTH` / `ERROR` |
| `usage` | `Usage` | token 用量 |
| `has_tool_calls` | `bool` | 是否有工具调用 |
| `has_content` | `bool` | 是否有文本回复 |

---

## 安全类

### Guardrail

```python
from agentkit import input_guardrail, output_guardrail, GuardrailResult

@input_guardrail
async def my_check(ctx):
    if "危险" in ctx.input:
        return GuardrailResult(triggered=True, reason="包含危险内容")
    return GuardrailResult(triggered=False)

@output_guardrail
async def my_output_check(ctx, output):
    return GuardrailResult(triggered=False)
```

**GuardrailResult**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `triggered` | `bool` | 是否触发熔断 |
| `reason` | `str \| None` | 触发原因 |
| `info` | `dict` | 附加信息 |

---

### PermissionPolicy

```python
from agentkit import PermissionPolicy

policy = PermissionPolicy(
    mode="ask",                    # "allow_all" / "deny_all" / "ask"
    allowed_tools={"read_file"},   # 白名单
    custom_check=my_check_fn,      # 自定义检查函数
)
```

| 参数 | 说明 |
|------|------|
| `mode="allow_all"` | 允许所有工具 |
| `mode="deny_all"` | 拒绝所有工具 |
| `mode="ask"` | 先查白名单，再调自定义检查 |

---

## 记忆类

### BaseMemoryProvider

记忆系统抽象接口。

```python
from agentkit import BaseMemoryProvider, Memory

class MyMemory(BaseMemoryProvider):
    async def add(self, content, *, user_id=None, agent_id=None, metadata=None) -> list[Memory]: ...
    async def search(self, query, *, user_id=None, agent_id=None, limit=10) -> list[Memory]: ...
    async def get_all(self, *, user_id=None, agent_id=None) -> list[Memory]: ...
    async def delete(self, memory_id) -> bool: ...
```

**内置实现**：`Mem0Provider`（需安装 `mem0ai`）

```python
from agentkit.memory.mem0_provider import Mem0Provider

memory = Mem0Provider({"vector_store": {"provider": "qdrant", ...}})
agent = Agent(memory=memory, ...)
```

Agent 会自动：
1. 对话前——检索相关记忆注入上下文
2. 对话后——提取新记忆存储

**Memory** 数据类：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 记忆 ID |
| `content` | `str` | 记忆内容 |
| `metadata` | `dict` | 元数据 |
| `score` | `float` | 相关性分数（检索时） |
