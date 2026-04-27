# AgentKit 架构设计

> 本文档介绍 AgentKit 框架的整体架构、分层设计、核心流程和设计决策。

---

## 目录

- [设计背景](#设计背景)
- [设计原则](#设计原则)
- [六层架构](#六层架构)
- [核心执行流程](#核心执行流程)
- [异步执行模型](#异步执行模型)
- [LLM 适配层设计](#llm-适配层设计)
- [Skill 三级加载机制](#skill-三级加载机制)
- [Agent 协作模型](#agent-协作模型)
- [记忆系统](#记忆系统)
- [性能优化](#性能优化)
- [安全机制](#安全机制)
- [项目目录结构](#项目目录结构)

---

## 设计背景

AgentKit 的设计基于对三大主流 Agent 框架源码的深入分析：

| 框架 | 借鉴的核心设计 |
|------|-------------|
| **Google ADK** | 三级渐进式 Skill 加载、SkillToolset 桥接模式、模板方法模式、Agent 树结构 |
| **OpenAI Agents SDK** | 声明式 Agent 定义、@function_tool 装饰器、Handoff + as_tool 双模式、Guardrail |
| **Anthropic Claude SDK** | 纯文件即 Skill、description 驱动触发、Hook 机制、权限分层 |

---

## 设计原则

| 原则 | 解释 |
|------|------|
| **声明式优先** | Agent / Tool / Skill 都是配置对象，而非命令式代码 |
| **Skill 一等公民** | Skill 不是 Tool 的子集，而是独立的能力抽象层 |
| **按需加载** | 三级加载模型，避免 token 浪费 |
| **双协作模式** | 同时支持 Handoff（转介）和 as_tool（委派） |
| **模型无关** | 自研 LLM 适配层，不绑定特定厂商 |
| **安全内置** | Guardrail、权限控制不是可选项，而是架构级考虑 |

---

## 六层架构

```
┌──────────────────────────────────────────────────────────────────┐
│ 第 1 层：Application（应用层）                                     │
│   Runner — 驱动 Agent 运行循环                                    │
│   RunContext — 运行上下文（session / state / user_id）             │
├──────────────────────────────────────────────────────────────────┤
│ 第 2 层：Agent（智能体层）                                         │
│   Agent — 核心 LLM Agent                                         │
│   SequentialAgent / ParallelAgent / LoopAgent — 编排 Agent        │
│   Handoff — Agent 间控制权转移                                     │
├──────────────────────────────────────────────────────────────────┤
│ 第 3 层：Skill（技能层）                                          │
│   SkillRegistry — 注册与发现                                      │
│   SkillToolset — Skill → Tool 桥接（4 个标准工具）                │
├──────────────────────────────────────────────────────────────────┤
│ 第 4 层：Tool（工具层）                                           │
│   FunctionTool / @function_tool — LLM 可调用的工具                │
│   BaseToolset — 工具集（可动态展开）                               │
├──────────────────────────────────────────────────────────────────┤
│ 第 5 层：Safety（安全层）                                         │
│   InputGuardrail / OutputGuardrail — 双向安全护栏                 │
│   PermissionPolicy — 三层权限控制                                 │
├──────────────────────────────────────────────────────────────────┤
│ 第 6 层：Foundation（基础设施层）                                  │
│   LLM 适配层 — 5 个适配器（OpenAI / Anthropic / Google / Ollama / │
│                 国内兼容），前缀自动路由                            │
│   LLMRegistry — 模型注册中心                                     │
│   MemoryProvider — 记忆系统（Mem0 集成）                          │
└──────────────────────────────────────────────────────────────────┘
```

**各层依赖关系**：

```
Application → Agent → Skill → Tool → Foundation
                ↓               ↓
              Safety          Safety
```

---

## 核心执行流程

当你调用 `Runner.run(agent, input="...")` 时，框架内部的完整流程如下：

```
用户输入
  │
  ▼
Runner.run()
  │
  ├─ 创建 RunContext
  │
  ├─ 检查输入护栏（InputGuardrail）
  │    └─ 如果触发 → 返回错误
  │
  ├─ 执行 Agent.run()
  │    │
  │    ├─ ❶ before_agent_callback
  │    │
  │    ├─ Agent._run_impl()（核心循环）
    │    │    │
    │    │    ├─ 加载 Skill 资源（触发所有 Skill 的 on_load 钩子）
    │    │    │
    │    │    ├─ 构建 instructions
    │    │    │    ├─ 静态字符串 或 动态函数
    │    │    │    ├─ 注入记忆（Memory 检索）
    │    │    │    └─ 注入 Skill 列表（L1 信息）
    │    │    │
    │    │    ├─ 汇总工具
    │    │    │    ├─ tools → FunctionTool
    │    │    │    ├─ skills → SkillToolset（4 个桥接工具）
    │    │    │    └─ handoffs → transfer_to_xxx
    │    │    │
    │    │    ├─ ❷ before_model_callback
    │    │    ├─ 调用 LLM（通过适配器）
    │    │    ├─ ❸ after_model_callback
    │    │    │
    │    │    ├─ 如果 LLM 发生错误：
    │    │    │    └─ ❾ on_error_callback
    │    │    │
    │    │    ├─ 如果 LLM 要调用工具：
    │    │    │    ├─ ❹ before_tool_callback
    │    │    │    ├─ 权限检查（PermissionPolicy）
    │    │    │    ├─ 执行工具
    │    │    │    ├─ ❺ after_tool_callback
    │    │    │    └─ 根据 tool_use_behavior 决定是否再调 LLM
    │    │    │
    │    │    ├─ 如果 LLM 要 handoff：
    │    │    │    ├─ ❻ before_handoff_callback
    │    │    │    ├─ 返回 handoff 事件 → Runner 切换 Agent
    │    │    │    └─ ❼ after_handoff_callback
    │    │    │
    │    │    ├─ 如果 LLM 给出最终回复：
    │    │    │    ├─ 输出最终结果
    │    │    │    └─ 存储记忆
    │    │    │
    │    │    └─ 释放 Skill 资源（触发所有 Skill 的 on_unload 钩子）
    │    │
    │    └─ ❽ after_agent_callback
    │
    ├─ 检查输出护栏（OutputGuardrail）
    │    └─ 如果触发 → 返回错误
    │
    └─ 返回 RunResult
```

**9 个回调点**标记为 ❶ ~ ❾，覆盖了 Agent、Model、Tool、Handoff 四个层面的前后拦截及错误处理（含 `on_error_callback`）。

补充说明：`after_agent_callback` 通过 `finally` 语义保证执行。即使上游编排发生提前 `return`（如 `escalate`）或外部关闭流式生成器（`aclose`），也会触发该回调；但在生成器关闭路径下，不保证回调事件继续对外 `yield`。

---

## Human-in-the-loop (HITL) 与状态管理

AgentKit 原生支持在任务执行过程中安全地挂起（Suspend）并持久化上下文，等待外部人工或异步信号介入后，再恢复（Resume）执行。

### 挂起与恢复机制

```
[Agent 运行中]
      │
      ├─ 遇到需要人工确认的工具 (抛出 HumanInputRequested)
      │
      ├─ Agent 捕获异常，注册 SuspensionRecord 并触发 suspend_requested 事件（含 suspension_id）
      │
      ├─ ContextStore 保存当前 RunContext (包含会话状态、执行分支、suspensions、resume_idempotency 等)
      │
      ▼
[进程可完全退出 / 释放资源]
      │
      ├─ 外部人工提供输入
      │
      ├─ Runner.resume(session_id, user_input, context_store, suspension_id=None, idempotency_key=None)
      │
      ├─ ContextStore 恢复 RunContext，按 suspension_id（或最新 pending）定位挂起点
      │    └─ resume_strategy=as_tool_result 时将 user_input 注入对应 tool_call 结果
      │
      ▼
[Agent 恢复运行，继续未完成的对话与工具链]
```

### 上下文存储 (ContextStore)

`ContextStore` 是用于管理 `RunContext` 持久化的核心协议。AgentKit 提供了两套开箱即用的实现：
- `InMemoryContextStore`：适用于单进程常驻的异步 Web 服务。
- `FileContextStore`：基于文件系统的持久化存储，支持跨进程断点续跑。

此外，`RunContext` 实现了标准的 `to_dict` / `from_dict` 序列化协议，并允许通过 `__ak_serialize__` 魔法方法安全序列化自定义的 `shared_context`。
从当前实现看，Checkpoint 不仅保存 `RunContext`，还会保存执行指针（`turn/max_turns/current_agent/agent_path`）；恢复时优先按 `agent_path` 回到挂起节点，并在挂起后额外发出 `suspended` 事件用于上层状态机对齐。

---

## 异步执行模型

### 设计原则

AgentKit 的**整个执行链都是异步的**——LLM 网络调用、工具执行、记忆检索都是异步 I/O，不阻塞线程。同时提供同步便捷入口，降低上手门槛。

### 内部架构

```
Runner.run_sync()          ← 同步入口（内部调 asyncio.run）
    │
    ▼
Runner.run()               ← 异步核心（async def）
    │
    ▼
Agent.run()                ← 异步生成器（async generator，yield Event）
    │
    ├─ LLM.generate()      ← 异步调用（await）
    ├─ Tool.execute()      ← 异步执行（await）
    └─ Memory.search()     ← 异步检索（await）
```

### 三种运行方式

| 方式 | API | 适用场景 |
|------|-----|---------|
| **同步** | `Runner.run_sync(agent, input=...)` | 脚本、快速测试、简单场景 |
| **异步** | `await Runner.run(agent, input=...)` | Web 服务、并发任务、生产环境 |
| **流式** | `async for event in Runner.run_streamed(agent, input=...)` | 实时展示进度、逐 token 输出 |

### 为什么选择异步优先？

1. **LLM 调用是 I/O 密集型**：一次 LLM 调用可能耗时几秒到几十秒，异步可以在等待期间处理其他请求
2. **并行 Agent 需要并发**：`ParallelAgent` 并行执行多个子 Agent，必须用 `asyncio.gather`
3. **工具可能涉及网络**：调用外部 API、数据库查询等都是异步操作
4. **`run_sync()` 兜底**：不熟悉异步的用户可以直接用同步入口，零学习成本

### 流式运行示例

```python
from agentkit.runner.events import EventType

async def main():
    async for event in Runner.run_streamed(agent, input="你好"):
        # 推荐使用 EventType 枚举匹配标准事件类型
        if event.type == EventType.LLM_RESPONSE:
            print("LLM 思考中...")
        elif event.type == EventType.TOOL_RESULT:
            # 配合 Schema 可进行强类型数据校验
            print(f"工具调用: {event.data}")
        elif event.type == EventType.FINAL_OUTPUT:
            print(f"最终回复: {event.data}")
```

### 事件协议与标准化 (Event Protocol)

在流式执行模型中，所有的节点变更、状态转换、信息传递都会被封装成统一的 `Event`。AgentKit 引入了 `EventType` 枚举和 Schema 校验能力，以保证处理复杂事件流时的健壮性。

- **强类型枚举**：内置 15+ 种标准事件类型（如 `suspend_requested`, `tool_call`, `loop_iteration`），同时底层类型基于 `str`，保留对任意自定义字符串事件的向后兼容。
- **Schema 校验 (`validate_data`)**：支持使用 Pydantic V1/V2 模型或原生 `dataclass` 对弱类型的 `event.data` 字典进行严格验证。
- **链路追踪 (`trace_path` / `parent_agent`)**：自动记录事件产生时的嵌套层级，方便排查多 Agent 协作中的调用链路问题。

---

## LLM 适配层设计

### 架构

```
Agent / Skill
     │
  LLMRegistry（前缀自动路由）
     │
  BaseLLM（统一抽象接口）
     │
  ┌──────────┬──────────┬──────────┬──────────┬────────────┐
  │ OpenAI   │Anthropic │ Google   │ Ollama   │ OpenAI兼容  │
  │ Adapter  │ Adapter  │ Adapter  │ Adapter  │  Adapter   │
  │ openai   │anthropic │google-genai│ aiohttp │ openai SDK │
  │  SDK     │  SDK     │   SDK    │         │+自定义base  │
  └────┬─────┘└────┬────┘└─────┬───┘└────┬───┘└──────┬─────┘
       │          │           │         │           │
    OpenAI   Anthropic    Google     Ollama      国内厂商
     API       API         API      本地API      API
```

### 前缀自动路由规则

| 模型标识前缀 | 适配器 |
|------------|--------|
| `gpt-`、`o1`、`o3`、`o4` | OpenAIAdapter |
| `claude-` | AnthropicAdapter |
| `gemini-` | GoogleAdapter |
| `ollama/` | OllamaAdapter |
| `deepseek/`、`qwen/`、`zhipu/`、`moonshot/`、`baichuan/`、`azure/` | OpenAICompatibleAdapter |

### 各厂商核心差异

| 维度 | OpenAI | Anthropic | Google | Ollama |
|------|--------|-----------|--------|--------|
| 工具参数格式 | JSON 字符串 | dict 对象 | dict 对象 | dict 对象 |
| system 消息 | 在 messages 中 | 单独 system 参数 | 单独 system_instruction | 在 messages 中 |
| 工具结果角色 | `role: "tool"` | `role: "user"` + tool_result 块 | `role: "user"` + function_response | `role: "tool"` |

**所有差异由适配器内部处理，上层代码完全不感知。**

---

## Skill 三级加载机制

```
┌─────────────────────────────────────────────────────────────┐
│ L1 — 发现层（始终在上下文中）                                 │
│ name + description，~100 词/Skill                            │
│ → LLM 据此判断是否需要使用某个 Skill                         │
├─────────────────────────────────────────────────────────────┤
│ L2 — 指令层（按需加载）                                      │
│ SKILL.md 正文，详细操作指令                                   │
│ → LLM 调用 load_skill 后加载                                 │
├─────────────────────────────────────────────────────────────┤
│ L3 — 资源层（按需加载）                                      │
│ references/ + assets/ + scripts/                             │
│ → 根据 L2 指令按需读取或执行                                  │
└─────────────────────────────────────────────────────────────┘
```

### SkillToolset 桥接

Skill 通过 SkillToolset 暴露为 4 个 LLM 可调用的标准工具：

| 工具 | 对应层级 | 功能 |
|------|---------|------|
| `list_skills` | L1 | 列出所有可用 Skill |
| `load_skill` | L2 | 加载 Skill 的详细操作指令 |
| `load_skill_resource` | L3 | 读取参考文档 / 资源文件 |
| `run_skill_script` | L3 | 执行 Skill 中的脚本 |

### Skill 与 Agent 的边界

| Agent | Skill |
|-------|-------|
| ✅ 有自己的 LLM 和对话循环 | ❌ 没有独立对话循环 |
| ✅ 可以 handoff | ❌ 不能独立被交接 |
| ✅ 有回调和护栏 | ❌ 借用 Agent 的 |
| 类比：工程师 | 类比：操作手册 |

---

## Agent 协作模型

### Handoff（转介）

```
Agent A ──[transfer_to_B]──→ Agent B（接管完整对话历史）
```

LLM 看到一个名为 `transfer_to_B` 的工具。调用时，Runner 将控制权完全交给 Agent B。

### as_tool（委派）

```
Agent A ──[call B.as_tool()]──→ Agent B ──[result]──→ Agent A
```

Agent B 被包装成一个 FunctionTool，以嵌套方式执行。完成后结果返回给 Agent A。

### 编排 Agent

| 编排器 | 行为 |
|--------|------|
| `SequentialAgent` | 按顺序执行子 Agent，A → B → C |
| `ParallelAgent` | 并行执行子 Agent（分支隔离），合并结果。支持 `early_exit` 提前取消分支机制 |
| `LoopAgent` | 循环执行直到某个子 Agent 发出 `escalate`、满足 `loop_condition`，或达到上限触发 `loop_exhausted` |

---

## 记忆系统

### 设计原则

AgentKit 的记忆系统遵循**可选、可插拔、自动化**三个原则：

- **可选**：默认不启用记忆，Agent 是无状态的。需要时通过 `memory=...` 配置
- **可插拔**：通过 `BaseMemoryProvider` 抽象接口，支持替换不同实现
- **自动化**：配好后框架自动在对话前检索、对话后存储，不需要额外代码

### 自动化流程

```
对话开始
  │
  ├─ memory.search(用户输入)         ← 自动检索相关记忆
  ├─ 将检索结果注入 system prompt    ← 作为「相关记忆」章节
  │
  ├─ Agent 正常执行（LLM 能看到记忆上下文）
  │
  ├─ memory.add(对话内容)             ← 自动存储新记忆
  │
  └─ 返回结果
```

### 两层实现

| 层级 | 类 | 说明 |
|------|-----|------|
| **抽象接口** | `BaseMemoryProvider` | 定义 `add/search/get_all/delete` 四个方法 |
| **内置实现** | `Mem0Provider` | 基于 Mem0，语义搜索 + 持久化（需向量数据库） |

用户可自行实现 `BaseMemoryProvider` 创建轻量记忆（如内存字典、SQLite、Redis 等），无需依赖 Mem0。

### 多用户隔离

通过 `user_id` 参数实现记忆隔离：

```python
# 不同用户的记忆互不干扰
await Runner.run(agent, input="我喜欢咖啡", user_id="user_A")
await Runner.run(agent, input="我喜欢茶", user_id="user_B")
```

---

## 性能优化

AgentKit 内置三项性能优化机制，可按场景组合使用。

### 1. Thinking 模式（Ollama）

部分模型（如 qwen3.5）支持「深度思考」模式。OllamaAdapter **默认开启** thinking。可以根据实际场景选择关闭。

```python
from agentkit.llm.registry import LLMRegistry

# 默认开启 thinking
llm = LLMRegistry.create("ollama/qwen3.5:cloud")

# 关闭 thinking（纯对话场景可能更快）
llm = LLMRegistry.create("ollama/qwen3.5:cloud")
llm.config.extra_params["think"] = False
agent = Agent(model=llm, ...)
```

> ⚠️ **注意事项**：
> - cloud 模型的 thinking 本身很快，关闭后工具调用场景可能反而更慢
> - 本地小模型（如 4b/9b）关闭 thinking 效果更显著（纯对话加速约 2-3 倍）
> - 建议先测试再决定是否关闭

### 2. LLM 响应缓存

对相同的输入（messages + tools 组合）缓存 LLM 响应，避免重复调用。使用内存 LRU 缓存，支持 TTL 过期。**默认开启**，缓存绑定 Agent 实例生命周期。

```python
# 默认已开启，无需额外配置
agent = Agent(model="ollama/qwen3.5:cloud", ...)

# 需要关闭时：
agent = Agent(model="ollama/qwen3.5:cloud", enable_cache=False, ...)

# 手动清空缓存：
agent.clear_cache()
```

**实测效果**：相同问题二次调用从秒级降至 **微秒级**。

> ⚠️ **注意事项**：
> - **不缓存工具调用响应**——因为工具结果可能随时间变化（如天气查询），只缓存纯文本回复
> - 适合 FAQ、重复查询等场景；不适合需要实时信息的场景
> - 缓存仅在单 Agent 实例内有效，重新创建 Agent 会清空缓存
> - 默认最大 128 条缓存，LRU 淘汰最久未使用的条目
> - 缓存实现内置 key 生成统计：`key_gen_calls / key_gen_total_ms / key_gen_last_ms / key_gen_avg_ms`

### 3. 记忆异步写入

默认情况下，记忆存储采用 fire-and-forget 模式——不等记忆写入完成就立即返回结果，后台异步完成写入。

```python
# 默认：异步写入（更快，适合 Web 服务等对响应时间敏感的场景）
agent = Agent(memory=my_memory, memory_async_write=True, ...)

# 同步写入（等写完再返回，适合多轮串行对话需要即时读取记忆的场景）
agent = Agent(memory=my_memory, memory_async_write=False, ...)
```

> ⚠️ **注意事项**：
> - `memory_async_write=True`（默认）时，下一轮对话可能还没读到上一轮刚存的记忆
> - 多轮串行对话（如示例 08）建议设为 `False`，确保记忆即时可用
> - Web 服务等并发场景建议保持 `True`，避免慢存储阻塞响应

### 三项优化的推荐组合

| 场景 | thinking | 缓存 | 记忆写入 |
|------|---------|------|---------|
| **Web 服务 / API** | 按需 | ✅ 开启 | 异步（默认） |
| **多轮聊天** | 保持开启 | ❌ 关闭 | 同步 |
| **FAQ / 客服** | 关闭 | ✅ 开启 | 异步 |
| **复杂推理任务** | 保持开启 | ❌ 关闭 | 按需 |

### 性能可观测性（新增）

当前实现已内置以下调试级性能观测点，便于后续压测与回归比对：

- `Agent` 每轮日志：`messages_build_ms`、`tool_defs_build_ms`、`cache_key_ms`
- `LLMCache` 统计字段：`key_gen_calls`、`key_gen_total_ms`、`key_gen_last_ms`、`key_gen_avg_ms`

---

## 安全机制

### 三层安全防护

```
┌─────────────────────────────────┐
│ 第 1 层：Guardrail（输入/输出）  │  → 检查用户输入和 Agent 输出
├─────────────────────────────────┤
│ 第 2 层：PermissionPolicy       │  → 控制哪些工具可被调用
├─────────────────────────────────┤
│ 第 3 层：脚本执行扩展层           │  → run_skill_script 预留 SandboxExecutor
│   当前：占位执行（不实际运行脚本）│
│   规划：Level 1/2/3 沙箱隔离      │
└─────────────────────────────────┘
```

### 关于 Docker：不是必须的

> ⚠️ **运行 Agent 不需要 Docker。** AgentKit 是纯 Python 框架，直接在本地 Python 环境即可运行。

当前版本 `run_skill_script` 为占位执行（不会实际执行脚本）。Docker 依赖用于后续 SandboxExecutor 落地时的 Level 3 扩展。以下是当前各场景的依赖说明：

| 场景 | 是否需要 Docker |
|------|:--------------:|
| 运行 Agent（纯对话） | ❌ |
| 运行带工具的 Agent（Function Calling） | ❌ |
| 运行带 Skill 的 Agent（仅指令，无脚本） | ❌ |
| Skill 脚本执行（当前占位实现） | ❌ |
| Skill 脚本执行（未来 Level 3 扩展） | 可选（届时 ✅） |

大部分 Skill 只使用「指令 + 工具」组合，完全不涉及脚本执行，因此不需要任何沙箱。

### 4. 扩展与隔离机制

#### 生命周期 Hooks / Callbacks
AgentKit 提供细粒度的执行拦截点，支持同步/异步回调，并允许请求与响应改写：
- **`before_agent_callback` / `after_agent_callback`**: 拦截整个 Agent 会话。`after_agent_callback` 在提前中断/外部关闭流的场景下也会执行（收尾保证），但关闭路径不保证继续外发 callback 事件。
- **`before_model_callback` / `after_model_callback`**: 在 LLM 调用前后拦截，允许改写 Prompt 和模型输出。
- **`before_tool_callback` / `after_tool_callback`**: 在工具执行前后拦截，允许改写执行结果。
- **`before_handoff_callback` / `after_handoff_callback`**: 在触发 Handoff 转移前拦截，可动态修改目标 Agent。
- **`on_error_callback`**: 捕获异常，通过 `fail_fast_on_hook_error` 配置决定是否中断流程。

#### 多租户隔离 (Multi-Tenant)
框架级支持 user/session 级数据隔离基线：
1. **`user_id` 与 `session_id` 贯穿**: 在 Memory、Skill、Tool 执行上下文（RunContext）中实现强隔离。
2. **Memory 自动分桶**: BaseMemoryProvider 强制按 `user_id` 进行存储和搜索。
3. **Session 资源释放监控**: 会话结束自动调用 Skill `on_unload(ctx)` 清理资源，并通过日志记录释放耗时。

---

## 项目目录结构

```
agentkit/
├── __init__.py              # 公共 API 导出
├── pyproject.toml           # 项目配置
│
├── agents/                  # Agent 层
│   ├── base_agent.py        #   BaseAgent（模板方法基类）
│   ├── agent.py             #   Agent（核心 LLM Agent）
│   └── orchestrators.py     #   Sequential / Parallel / Loop
│
├── tools/                   # Tool 层
│   ├── base_tool.py         #   BaseTool / BaseToolset
│   ├── function_tool.py     #   FunctionTool / @function_tool
│   ├── structured_data.py   #   StructuredDataTool / ResultFormatter
│   ├── sqlite_tool.py       #   SQLiteTool
│   ├── nebula_tool.py       #   NebulaGraphTool
│   ├── graph/               #   统一图接口层（Adapter/Repository/Tool）
│   │   ├── protocols.py     #     GraphAdapter 协议
│   │   ├── repository.py    #     GraphRepository（统一访问入口）
│   │   ├── factory.py       #     create_graph_repository* 工厂
│   │   ├── networkx_adapter.py
│   │   ├── litegraph_adapter.py
│   │   ├── nebula_adapter.py
│   │   └── tool.py          #     GraphQueryTool
│   └── skill_toolset.py     #   SkillToolset（4 个桥接工具）
│
├── skills/                  # Skill 层
│   ├── models.py            #   Skill / SkillFrontmatter / SkillResources
│   ├── loader.py            #   load_skill_from_dir
│   └── registry.py          #   SkillRegistry
│
├── llm/                     # LLM 适配层
│   ├── types.py             #   统一类型系统
│   ├── base.py              #   BaseLLM 抽象接口
│   ├── registry.py          #   LLMRegistry（前缀路由）
│   ├── middleware.py         #   RetryMiddleware / CostTracker
│   └── adapters/
│       ├── openai_adapter.py
│       ├── anthropic_adapter.py
│       ├── google_adapter.py
│       ├── ollama_adapter.py
│       └── openai_compatible.py
│
├── runner/                  # Runner 层
│   ├── runner.py            #   Runner（核心循环）
│   ├── context.py           #   RunContext
│   ├── context_store.py     #   ContextStore / InMemory / File
│   └── events.py            #   Event / EventType / RunResult
│
├── safety/                  # 安全层
│   ├── guardrails.py        #   InputGuardrail / OutputGuardrail
│   └── permissions.py       #   PermissionPolicy
│
├── memory/                  # 记忆系统
│   ├── base.py              #   BaseMemoryProvider
│   └── mem0_provider.py     #   Mem0Provider
│
├── utils/
│   └── schema.py            #   函数签名 → JSON Schema
│
├── examples/                # 示例
│   ├── standard/            #   标准版示例（01-18，含 8A/8B/8C、9A/9B/9C）
│   ├── ollama/              #   Ollama 版示例（01-19，含 8A/8B/8C、9A/9B/9C）
│   ├── quickstart.py
│   └── test_ollama.py
│
└── docs/                    # 文档
    ├── README.md
    ├── QuickStart.md
    ├── Architecture.md
    └── Reference.md
```
