# AgentKit 快速入门教程

> 本教程将带你从零开始，通过 18 组由简到繁的示例（含 8A/8B/8C、9A/9B/9C），掌握 AgentKit 的核心用法。

---

## 目录

- [环境准备](#环境准备)
  - [安装依赖](#1-安装依赖)
  - [配置模型](#2-配置模型)
  - [关于运行环境](#4-关于运行环境)
  - [同步与异步](#5-同步与异步)
- [示例 1：最简 Agent — 纯对话](#示例-1最简-agent--纯对话)
- [示例 2：带工具的 Agent — Function Calling](#示例-2带工具的-agent--function-calling)
- [示例 3：带 Skill 的 Agent — 领域知识包](#示例-3带-skill-的-agent--领域知识包)
- [示例 4：多 Agent 协作 — Handoff 与 as_tool](#示例-4多-agent-协作--handoff-与-as_tool)
- [示例 5：安全护栏 — Guardrail 与权限控制](#示例-5安全护栏--guardrail-与权限控制)
- [示例 6：编排 Agent — 流水线与循环](#示例-6编排-agent--流水线与循环)
- [示例 7：同步/异步/流式运行](#示例-7同步异步流式运行)
- [示例 8：记忆系统 — 跨会话长期记忆](#示例-8记忆系统--跨会话长期记忆)
- [示例 9A：关系型数据库 — 防止 SQL 注入的参数化 Tool](#示例-9a关系型数据库--防止-sql-注入的参数化-tool)
- [示例 9B：图数据库 — 配合 Mock 运行的 NebulaGraphTool](#示例-9b图数据库--配合-mock-运行的-nebulagraphtool)
- [示例 9C：NebulaGraphTool 最小可执行示例（工具层直调）](#示例-9cnebulagraphtool-最小可执行示例工具层直调)
- [示例 10：Skill 生命周期 — 管理外部资源连接池](#示例-10skill-生命周期--管理外部资源连接池)
- [示例 11：编排增强 — 循环退出条件与并行提前终止](#示例-11编排增强--循环退出条件与并行提前终止)
- [示例 12：RunContext 序列化与共享状态](#示例-12runcontext-序列化与共享状态)
- [示例 13：Human-in-the-loop 与断点续跑](#示例-13human-in-the-loop-与断点续跑)
- [示例 14：事件协议标准化与强类型校验](#示例-14事件协议标准化与强类型校验)
- [示例 15：多租户隔离 (Multi-Tenant Isolation)](#15-多租户隔离-multi-tenant-isolation)
- [示例 16：生命周期 Hooks 与 Callbacks](#16-生命周期-hooks-与-callbacks)
- [示例 17：Checkpoint 深度恢复（Handoff 后挂起与原路径恢复）](#17-checkpoint-深度恢复handoff-后挂起与原路径恢复)
- [示例 18：ModelCosplay（运行时改写预设模型）](#18-modelcosplay运行时改写预设模型)
- [性能提示](#性能提示)
- [使用不同的 LLM](#使用不同的-llm)
- [下一步](#下一步)

---

## 环境准备

### 1. 安装依赖

```bash
# 基础安装
pip install ni.agentkit

# 如果需要 OpenAI / DeepSeek / 通义千问等
pip install "ni.agentkit[openai]"
```

### 2. 配置模型

AgentKit 支持多种 LLM。选择一种即可：

**方式 A：本地 Ollama（推荐入门，无需 API Key）**

```bash
# 安装 Ollama: https://ollama.com
ollama pull qwen3.5:cloud
```

**方式 B：OpenAI**

```bash
pip install openai>=1.0.0
export OPENAI_API_KEY="sk-..."
```

**方式 C：DeepSeek（国内推荐）**

```bash
pip install openai>=1.0.0
export DEEPSEEK_API_KEY="sk-..."
```

### 3. 验证安装

```python
from agentkit import Agent, Runner, function_tool
print("✅ AgentKit 安装成功")
```

### 4. 关于运行环境

> 💡 **AgentKit 是纯 Python 框架，不需要 Docker。** 直接在本地 Python 环境运行即可。
>
> 当前版本中 `run_skill_script` 仍是占位执行（返回占位结果，不实际运行脚本），因此日常使用通常不需要 Docker。详见 [Architecture.md](Architecture.md) 中的安全机制说明。

### 5. 同步与异步

AgentKit 底层是异步的，但提供了三种运行方式：

```python
# 方式 1：同步运行（最简单，推荐入门使用）
result = Runner.run_sync(agent, input="你好")

# 方式 2：异步运行（推荐生产环境）
import asyncio
async def main():
    result = await Runner.run(agent, input="你好")
asyncio.run(main())

# 方式 3：流式运行（实时获取事件）
async def main():
    async for event in Runner.run_streamed(agent, input="你好"):
        if event.type == "final_output":
            print(event.data)
```

| 方式 | 适用场景 |
|------|---------|
| `Runner.run_sync()` | 脚本、快速测试、学习入门 |
| `await Runner.run()` | Web 服务、并发任务 |
| `Runner.run_streamed()` | 实时展示进度、聊天界面 |

> 本教程的示例统一使用 `Runner.run_sync()` 以保持简洁。

---

## 示例 1：最简 Agent — 纯对话

最简单的 Agent 只需要三个参数：名称、指令、模型。

```python
from agentkit import Agent, Runner

agent = Agent(
    name="assistant",
    instructions="你是一个有帮助的中文助手。回答尽量简洁。",
    model="ollama/qwen3.5:cloud",   # 替换为你使用的模型
)

# 同步运行
result = Runner.run_sync(agent, input="什么是量子计算？请用一句话解释。")

if result.success:
    print(f"回复: {result.final_output}")
else:
    print(f"错误: {result.error}")
```

**要点**：
- `Agent` 是一个声明式配置对象，不需要继承任何类
- `Runner.run_sync()` 是同步入口，内部使用 `asyncio.run()`
- `result.success` 检查是否成功，`result.final_output` 获取输出

### 异步运行

```python
import asyncio

async def main():
    result = await Runner.run(agent, input="你好")
    print(result.final_output)

asyncio.run(main())
```

---

## 示例 2：带工具的 Agent — Function Calling

用 `@function_tool` 装饰器将 Python 函数变成 LLM 可调用的工具。

```python
from agentkit import Agent, Runner, function_tool

# 用装饰器定义工具 —— 一行搞定
@function_tool
def add(a: int, b: int) -> str:
    """两个数字相加"""
    return str(a + b)

@function_tool
def multiply(a: int, b: int) -> str:
    """两个数字相乘"""
    return str(a * b)

@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    weather_data = {
        "北京": "晴，25°C",
        "上海": "多云，22°C",
        "深圳": "阵雨，28°C",
    }
    return weather_data.get(city, f"{city}：暂无数据")

# 创建带工具的 Agent
agent = Agent(
    name="smart-assistant",
    instructions="你是一个全能助手。可以做数学计算和查天气。根据用户需求选择合适的工具。",
    model="ollama/qwen3.5:cloud",
    tools=[add, multiply, get_weather],   # 直接传入工具列表
)

result = Runner.run_sync(agent, input="请计算 15 + 27 的结果")
print(result.final_output)  # "42" 或 "15 + 27 = 42"

result = Runner.run_sync(agent, input="北京今天天气如何？")
print(result.final_output)  # "北京今天晴，气温25°C"
```

**要点**：
- `@function_tool` 自动从函数签名推断 JSON Schema，从 docstring 提取描述
- 支持 `needs_approval=True`（需要人工审批）和 `timeout=30`（超时秒数）
- 工具函数可以是同步或异步的

### 带参数的装饰器

```python
@function_tool(needs_approval=True, timeout=30)
async def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件（需要人工确认）"""
    # ... 实际发送逻辑
    return "邮件已发送"
```

---

## 示例 3：带 Skill 的 Agent — 领域知识包

**Skill 是 AgentKit 的核心创新**——它是"指令 + 资源 + 脚本"的打包体，代表一个领域的专业知识。

### 方式 A：代码中直接定义 Skill

```python
from agentkit import Agent, Runner, Skill, SkillFrontmatter, function_tool

# 定义一个天气分析 Skill
weather_skill = Skill(
    frontmatter=SkillFrontmatter(
        name="weather-analysis",
        description="天气分析技能，查询天气并给出穿衣建议",
    ),
    instructions="""## 天气分析步骤

1. 使用 get_weather 工具查询用户指定城市的天气
2. 根据天气情况给出穿衣建议：
   - 温度 > 30°C：建议穿短袖
   - 温度 20-30°C：建议穿薄外套
   - 温度 < 20°C：建议穿厚外套
3. 用简洁的中文回复用户""",
)

@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return {"北京": "晴，25°C", "深圳": "阵雨，28°C"}.get(city, f"{city}：暂无数据")

# 创建带 Skill 的 Agent
agent = Agent(
    name="skill-agent",
    instructions="你是一个智能助手，可以使用专业技能来完成任务。",
    model="ollama/qwen3.5:cloud",
    skills=[weather_skill],      # ⭐ Skill 一等公民
    tools=[get_weather],
)

result = Runner.run_sync(agent, input="深圳今天适合穿什么衣服？")
print(result.final_output)
# 输出类似："深圳今天阵雨，气温28°C，建议穿薄外套。"
```

### 方式 B：从目录加载 Skill

创建 Skill 目录结构：

```
skills/weather-analysis/
├── SKILL.md              # 必须
├── references/           # 可选
│   └── clothing_guide.md
└── scripts/              # 可选
    └── analyze.py
```

`SKILL.md` 内容：

```markdown
---
name: weather-analysis
description: 天气分析技能，查询天气并给出穿衣建议
metadata:
  additional_tools:
    - get_weather
---

## 天气分析步骤

1. 使用 get_weather 工具查询天气
2. 读取 references/clothing_guide.md 获取穿衣建议规则
3. 用简洁的中文回复用户
```

加载并使用：

```python
from agentkit import Agent, Runner, load_skill_from_dir

weather_skill = load_skill_from_dir("./skills/weather-analysis")

agent = Agent(
    name="skill-agent",
    model="ollama/qwen3.5:cloud",
    skills=[weather_skill],
)
```

### Skill 三级加载机制

AgentKit 的 Skill 采用三级渐进式加载，避免浪费 token：

| 级别 | 内容 | 加载时机 | Token 开销 |
|------|------|---------|-----------|
| **L1** | name + description | Agent 启动时自动注入 | ~100 词/Skill |
| **L2** | SKILL.md 详细指令 | LLM 调用 `load_skill` 时 | ~500 行 |
| **L3** | references/assets/scripts | 指令要求时按需加载 | 不限 |

---

## 示例 4：多 Agent 协作 — Handoff 与 as_tool

AgentKit 支持两种 Agent 协作模式：

### 模式 A：as_tool（委派）

一个 Agent 把另一个 Agent 当作工具调用。调用后控制权返回原 Agent。

```python
from agentkit import Agent, Runner

# 专家 Agent
researcher = Agent(
    name="researcher",
    instructions="你是一个研究助手。收到问题后，给出简短的研究结论。",
    model="ollama/qwen3.5:cloud",
)

# 主管 Agent，把研究员当工具用
manager = Agent(
    name="manager",
    instructions="你是项目经理。需要研究信息时调用 research 工具。综合研究结果给出建议。",
    model="ollama/qwen3.5:cloud",
    tools=[
        researcher.as_tool("research", "调用研究助手获取研究信息"),
    ],
)

result = Runner.run_sync(manager, input="帮我调研 Python 异步编程的最佳实践")
print(result.final_output)
```

### 模式 B：Handoff（转介）

一个 Agent 把整个对话移交给另一个 Agent，控制权完全转移。

```python
billing_agent = Agent(
    name="billing",
    instructions="你是账单专家，处理所有账单相关问题。",
    model="ollama/qwen3.5:cloud",
)

tech_agent = Agent(
    name="tech",
    instructions="你是技术支持，处理所有技术问题。",
    model="ollama/qwen3.5:cloud",
)

triage_agent = Agent(
    name="triage",
    instructions="你是客服分诊员。根据用户问题，转交给合适的专家。账单问题转给billing，技术问题转给tech。",
    model="ollama/qwen3.5:cloud",
    handoffs=[billing_agent, tech_agent],
)

result = Runner.run_sync(triage_agent, input="我的账单金额好像不对")
print(f"最终由 {result.last_agent} 处理: {result.final_output}")
```

### 两种模式对比

| | Handoff（转介） | as_tool（委派） |
|--|---------------|---------------|
| **控制权** | 完全转移 | 调用后返回 |
| **对话历史** | 目标收到完整历史 | 目标只收到任务输入 |
| **类比** | 把患者转到专科 | 打电话问专家一个问题 |

---

## 示例 5：安全护栏 — Guardrail 与权限控制

### 输入护栏

```python
from agentkit import Agent, Runner, input_guardrail, GuardrailResult

@input_guardrail
async def block_sensitive_words(ctx):
    """检查输入是否包含敏感词"""
    sensitive = ["密码", "身份证", "银行卡号"]
    for word in sensitive:
        if word in ctx.input:
            return GuardrailResult(triggered=True, reason=f"包含敏感词: {word}")
    return GuardrailResult(triggered=False)

agent = Agent(
    name="safe-agent",
    instructions="你是一个安全的助手。",
    model="ollama/qwen3.5:cloud",
    input_guardrails=[block_sensitive_words],
)

result = Runner.run_sync(agent, input="请告诉我你的密码")
print(result.error)  # "输入被安全护栏拦截: 包含敏感词: 密码"
```

### 输出护栏

```python
from agentkit import output_guardrail, GuardrailResult

@output_guardrail
async def check_factual_accuracy(ctx, output):
    """检查输出是否存在问题"""
    if "我不确定" in str(output):
        return GuardrailResult(triggered=True, reason="输出包含不确定内容")
    return GuardrailResult(triggered=False)

agent = Agent(
    name="safe-agent",
    output_guardrails=[check_factual_accuracy],
    # ...
)
```

### 权限控制

```python
from agentkit import PermissionPolicy

agent = Agent(
    name="controlled-agent",
    model="ollama/qwen3.5:cloud",
    tools=[send_email, read_file, delete_file],
    permission_policy=PermissionPolicy(
        mode="ask",                              # "allow_all" / "deny_all" / "ask"
        allowed_tools={"read_file"},             # 白名单：只允许 read_file
    ),
)
```

---

## 示例 6：编排 Agent — 流水线与循环

### 顺序执行（SequentialAgent）

```python
from agentkit import Agent, SequentialAgent, Runner

pipeline = SequentialAgent(
    name="report-pipeline",
    sub_agents=[
        Agent(name="extractor", instructions="从用户输入中提取关键数据点", model="ollama/qwen3.5:cloud"),
        Agent(name="analyzer", instructions="分析提取的数据，找出趋势和规律", model="ollama/qwen3.5:cloud"),
        Agent(name="reporter", instructions="将分析结果写成一段简洁的报告", model="ollama/qwen3.5:cloud"),
    ],
)

result = Runner.run_sync(pipeline, input="今年Q1销售额1000万，Q2增长到1500万，Q3下降到1200万")
```

### 并行执行（ParallelAgent）

```python
from agentkit import ParallelAgent

parallel = ParallelAgent(
    name="multi-analysis",
    sub_agents=[
        Agent(name="financial", instructions="分析财务数据", model="ollama/qwen3.5:cloud"),
        Agent(name="market", instructions="分析市场趋势", model="ollama/qwen3.5:cloud"),
        Agent(name="risk", instructions="分析风险因素", model="ollama/qwen3.5:cloud"),
    ],
)
```

### 循环执行（LoopAgent）

```python
from agentkit import LoopAgent

# 进阶特性：支持自定义退出条件与事件增强
def check_status(ctx, state):
    # state["iteration"] 包含当前轮次
    return True

review_loop = LoopAgent(
    name="code-review",
    max_iterations=5,
    loop_condition=check_status, # 可选：每次循环前调用的回调函数
    sub_agents=[
        Agent(name="coder", instructions="根据反馈编写代码", model="ollama/qwen3.5:cloud"),
        Agent(name="reviewer", instructions="审查代码。通过发 escalate", model="ollama/qwen3.5:cloud"),
    ],
)
```

> **增强提示**：当 `ParallelAgent` 设置 `early_exit=True` 时，如果某个子 Agent 触发了 `escalate` 升级事件，它将自动取消其他尚未执行完的分支，并产出 `parallel_early_exit` 事件。当 `LoopAgent` 达到 `max_iterations` 上限时，将产出明确的 `loop_exhausted` 事件。

---

## 示例 7：同步/异步/流式运行

前面的示例统一使用 `Runner.run_sync()` 保持简洁。本示例展示 Runner 的三种运行方式及其适用场景。

### 方式 1：同步运行（最简单）

```python
from agentkit import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """获取天气"""
    return {"北京": "晴，25°C", "上海": "多云，22°C"}.get(city, f"{city}：暂无数据")

agent = Agent(
    name="assistant",
    instructions="你是一个简洁的中文助手。",
    model="ollama/qwen3.5:cloud",
    tools=[get_weather],
)

# 一行搞定，内部自动处理 asyncio
result = Runner.run_sync(agent, input="北京今天天气如何？")
print(result.final_output)
```

`run_sync()` 适合**脚本、快速测试、学习入门**。

### 方式 2：异步运行（推荐生产环境）

```python
import asyncio

async def main():
    result = await Runner.run(agent, input="上海今天天气如何？")
    print(result.final_output)

asyncio.run(main())
```

异步的核心优势——**并发执行多个请求**：

```python
async def concurrent_demo():
    queries = ["1+1等于几？", "北京天气如何？", "什么是 Python？"]

    # asyncio.gather 并发执行 3 个请求
    results = await asyncio.gather(*[
        Runner.run(agent, input=q) for q in queries
    ])

    for q, r in zip(queries, results):
        print(f"  [{q}] → {r.final_output}")

asyncio.run(concurrent_demo())
```

> 3 个请求并发总耗时 ≈ 单个请求的时间，而非 3 倍。

### 方式 3：流式运行（实时事件）

```python
import asyncio

async def stream_demo():
    async for event in Runner.run_streamed(agent, input="北京今天天气如何？"):
        if event.type == "llm_response":
            has_tools = "有工具调用" if event.data.has_tool_calls else "纯文本"
            print(f"🤖 LLM 响应 ({has_tools})")
        elif event.type == "tool_result":
            tool_name = event.data.get("tool", "?")
            print(f"🔧 工具 {tool_name} → {event.data.get('result', '')}")
        elif event.type == "final_output":
            print(f"✅ 最终输出: {event.data}")

asyncio.run(stream_demo())
```

适合**聊天界面、进度展示**——每个事件实时推送。

### 三种方式对比

| 方式 | API | 适用场景 |
|------|-----|---------|
| **同步** | `Runner.run_sync(agent, input=...)` | 脚本、快速测试 |
| **异步** | `await Runner.run(agent, input=...)` | Web 服务、并发任务 |
| **流式** | `async for event in Runner.run_streamed(...)` | 聊天 UI、进度展示 |

> ⚠️ **注意**：`run_sync()` 内部调用 `asyncio.run()`，不能在已有事件循环中使用。如果你的代码已经是 `async` 的，请直接用 `await Runner.run()`。

---

## 示例 8：记忆系统 — 跨会话长期记忆

默认情况下，Agent 每次运行都是无状态的。配上记忆后，Agent 可以记住用户的偏好和历史。

### 8A：SimpleMemory

```python
from agentkit import Agent, Runner, BaseMemoryProvider, Memory

class SimpleMemory(BaseMemoryProvider):
    def __init__(self):
        self._store, self._counter = [], 0
    async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
        self._counter += 1
        m = Memory(id=str(self._counter), content=content)
        self._store.append(m)
        return [m]
    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        query_words = set(query)
        scored = [(len(query_words & set(m.content)), m) for m in self._store]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [m for s, m in scored[:limit] if s > 0]
    async def get_all(self, *, user_id=None, agent_id=None):
        return list(self._store)
    async def delete(self, memory_id):
        self._store = [m for m in self._store if m.id != memory_id]
        return True

memory = SimpleMemory()
agent = Agent(
    name="personal-assistant",
    instructions="你是一个贴心的个人助手。根据记忆来个性化回答。",
    model="ollama/qwen3.5:cloud",
    memory=memory,
    memory_async_write=False,
)

Runner.run_sync(agent, input="我叫小明，我喜欢喝咖啡，讨厌喝茶", user_id="krix")
result = Runner.run_sync(agent, input="帮我推荐一杯饮料", user_id="krix")
print(result.final_output)  # 基于记忆推荐
```

### 8B：Mem0Provider（生产级）

```bash
pip install mem0ai
docker run -p 6333:6333 qdrant/qdrant   # 启动向量数据库
```

```python
from agentkit.memory.mem0_provider import Mem0Provider

memory = Mem0Provider({
    "vector_store": {
        "provider": "qdrant",
        "config": {"collection_name": "my_agent", "host": "localhost", "port": 6333}
    }
})

agent = Agent(memory=memory, ...)  # 先构建 memory，再注入 Agent
```

Mem0 相比 SimpleMemory 的优势：**语义搜索**（理解意思而非关键词）、**持久化**（重启不丢失）、**智能提取**（从对话中自动抽取关键信息）。

### 8C：自定义 Memory（文件持久化）

```python
import json
from pathlib import Path
from agentkit import BaseMemoryProvider, Memory, Agent

class FileMemoryProvider(BaseMemoryProvider):
    def __init__(self, file_path: str):
        self.path = Path(file_path)
        self.records = json.loads(self.path.read_text()) if self.path.exists() else []
    async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
        new_id = str(len(self.records) + 1)
        self.records.append({"id": new_id, "content": content, "user_id": user_id})
        self.path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2))
        return [Memory(id=new_id, content=content)]
    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        q = query.lower()
        out = [r for r in self.records if q in r["content"].lower()]
        return [Memory(id=r["id"], content=r["content"]) for r in out[:limit]]
    async def get_all(self, *, user_id=None, agent_id=None):
        return [Memory(id=r["id"], content=r["content"]) for r in self.records]
    async def delete(self, memory_id):
        self.records = [r for r in self.records if r["id"] != memory_id]
        self.path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2))
        return True

memory = FileMemoryProvider("/tmp/agentkit_memory.json")
agent = Agent(memory=memory, ...)
```

**要点**：
- 默认不开启记忆，需要给 `Agent` 传 `memory=...` 参数
- `SimpleMemory` 适合开发测试，`Mem0Provider` 适合生产语义检索
- 自定义 `FileMemoryProvider` 可实现轻量持久化（进程重启后仍可读取）

---

## 示例 9A：关系型数据库 — 防止 SQL 注入的参数化 Tool

传统方法让 LLM 直接输出 SQL 存在严重安全隐患（如注入攻击）或语法错误。
AgentKit 提供了 `StructuredDataTool` 基类，采用**参数化查询模式**。LLM 只需要输出经过 Pydantic 校验的结构化参数，底层的查询语句拼接和执行由代码严格控制。

以下以 SQLite 为例：

```python
import asyncio
import sqlite3
from pydantic import BaseModel, Field
from agentkit import Agent, Runner

# 导入 SQLite 参数化查询工具
from agentkit.tools.sqlite_tool import SQLiteTool

# 1. 准备 Mock 数据库
DB_PATH = "/tmp/agentkit_demo.db"
conn = sqlite3.connect(DB_PATH)
conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, role TEXT, age INTEGER)")
conn.execute("INSERT INTO users (name, role, age) VALUES ('Alice', 'Admin', 30), ('Bob', 'User', 25)")
conn.commit()

# 2. 定义严格的参数 Schema，让 LLM 只需要输出参数
class UserRoleQueryArgs(BaseModel):
    role: str = Field(..., description="要查询的用户角色名称，例如 'Admin' 或 'User'")

# 3. 实例化参数化工具
# query_template 决定了底层查询逻辑，LLM 无法篡改它。使用 :role 作为安全占位符
sqlite_tool = SQLiteTool(
    name="query_users_by_role",
    description="根据角色查询用户信息",
    parameters_schema=UserRoleQueryArgs,
    query_template="SELECT name, age FROM users WHERE role = :role;",
    db_path=DB_PATH,
)

async def main():
    agent = Agent(
        name="DBAssistant",
        instructions="你是一个数据库查询助手，请帮用户查询数据库。如果查询成功，请用中文自然地回复查询结果。",
        model="ollama/qwen3.5:cloud",
        tools=[sqlite_tool],
    )
    result = await Runner.run(agent, input="请帮我查一下角色为 User 的人有哪些？")
    print(f"🤖 回复:\n{result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
```

**要点**：
- `StructuredDataTool` 自动将数据库原生返回标准化为 LLM 可读的 JSON 格式。
- LLM 只负责抽取参数，彻底杜绝了注入风险。

---

## 示例 9B：图数据库 — 配合 Mock 运行的 NebulaGraphTool

AgentKit 内置了对图数据库（如 Nebula Graph）的结构化支持。如果你尚未安装真实的数据库集群，也可以通过 Mock 来验证逻辑。

```python
import asyncio
from typing import Any
from pydantic import BaseModel, Field
from agentkit import Agent, Runner

from agentkit.tools.structured_data import ResultFormatter
from agentkit.tools.nebula_tool import NebulaGraphTool

# 1. 简单的 Mock 客户端与结果格式化器
class MockSession:
    def execute(self, query: str):
        print(f"[Nebula Session] 执行 GQL: {query}")
        return "mock_result"
    def release(self): pass

class MockConnectionPool:
    def get_session(self, user, pwd): return MockSession()

class MockResultFormatter(ResultFormatter):
    def format(self, raw_result: Any) -> Any:
        return {"summary": "Query succeeded", "data": [{"friend_name": "Bob"}]}

# 2. 定义参数 Schema 与工具
class PersonQueryArgs(BaseModel):
    name: str = Field(..., description="要查找的人的名字", pattern=r"^[A-Za-z0-9_]+$")

nebula_tool = NebulaGraphTool(
    name="find_person_friends",
    description="在知识图谱中查找某个人的朋友",
    parameters_schema=PersonQueryArgs,
    query_template='MATCH (v:person)-[:friend]->(e:person) WHERE id(v) == "{name}" RETURN e.name AS friend_name;',
    space_name="social_graph",
    connection_pool=MockConnectionPool(), # 注入 Mock 连接池
    formatter=MockResultFormatter(),      # 注入 Mock 格式化器
)

async def main():
    agent = Agent(
        name="GraphAssistant",
        instructions="你是一个图数据库查询助手，请帮我查询并总结结果。",
        model="ollama/qwen3.5:cloud",
        tools=[nebula_tool],
    )
    result = await Runner.run(agent, input="帮我找一下 Alice 的朋友。")
    print(f"🤖 回复:\n{result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
```

**要点**：
- 无论是关系型还是图数据库，都可以通过统一的 `StructuredDataTool` 架构进行管理。
- 可以灵活注入外部 `connection_pool` 与 `formatter`。

---

## 示例 9C：NebulaGraphTool 最小可执行示例（工具层直调）

如果你想先验证 `NebulaGraphTool` 本身（参数校验、查询模板拼接、formatter 输出）是否工作正常，可以不经过 LLM，直接调用工具执行。

```python
import asyncio
from typing import Any
from pydantic import BaseModel, Field
from agentkit.runner.context import RunContext
from agentkit.tools.nebula_tool import NebulaGraphTool
from agentkit.tools.structured_data import ResultFormatter

class MockSession:
    def execute(self, query: str):
        print(f"[MockSession] execute gql => {query}")
        return "mock_result_set"
    def release(self): pass

class MockConnectionPool:
    def get_session(self, user, password):
        return MockSession()

class MockNebulaFormatter(ResultFormatter):
    def format(self, raw_result: Any) -> Any:
        return {"summary": "Query succeeded (mock)", "data": [{"friend_name": "Bob"}]}

class PersonQueryArgs(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z0-9_]+$")

nebula_tool = NebulaGraphTool(
    name="find_person_friends",
    description="查询某个人在图谱中的朋友关系",
    parameters_schema=PersonQueryArgs,
    query_template='MATCH (v:person)-[:friend]->(e:person) WHERE id(v) == "{name}" RETURN e.name AS friend_name;',
    space_name="social_graph",
    connection_pool=MockConnectionPool(),
    formatter=MockNebulaFormatter(),
)

async def main():
    payload = await nebula_tool.execute(RunContext(input="demo"), {"name": "Alice_001"})
    print(payload)

if __name__ == "__main__":
    asyncio.run(main())
```

运行文件：
- `examples/standard/09c_nebula_graph_tool.py`
- `examples/ollama/09c_nebula_graph_tool.py`

**要点**：
- 该示例不依赖真实 Nebula 集群，也不依赖 LLM，可用于本地快速验证 Tool 行为。
- 后续接入真实 Nebula 时，只需替换 `connection_pool` 与（可选）`formatter`。

---

## 示例 10：Skill 生命周期 — 管理外部资源连接池

当 Skill 依赖外部资源（如数据库连接池、长期会话句柄）时，你需要确保在使用前正确初始化，并在结束时安全释放。
AgentKit 为 Skill 提供了 `on_load_hook` 和 `on_unload_hook` 生命周期钩子。

```python
import asyncio
import logging
from agentkit import Agent, Runner, Skill, SkillFrontmatter

logging.basicConfig(level=logging.INFO)

# 1. 定义初始化和释放资源的钩子
async def init_resource(skill: Skill):
    logging.info(f"[{skill.name}] on_load_hook: 建立数据库连接池...")
    # 将资源绑定到 Skill 的专属上下文 context 中
    skill.context["db_pool"] = "MockConnectionPool(size=10)"

async def close_resource(skill: Skill):
    logging.info(f"[{skill.name}] on_unload_hook: 释放连接池...")
    pool = skill.context.get("db_pool")
    if pool:
        logging.info(f"[{skill.name}] 已成功关闭连接池: {pool}")
        skill.context.clear()

# 2. 创建带钩子的 Skill
db_skill = Skill(
    frontmatter=SkillFrontmatter(
        name="database-skill",
        description="提供数据库查询能力，包含连接池生命周期管理",
    ),
    instructions="你可以使用数据库资源进行操作",
    on_load_hook=init_resource,
    on_unload_hook=close_resource,
)

async def main():
    agent = Agent(
        name="assistant",
        instructions="你是一个助手。",
        model="ollama/qwen3.5:cloud",
        skills=[db_skill],
    )
    
    print("开始运行 Agent，观察控制台的生命周期日志：\n")
    # 运行前后会自动触发 on_load 和 on_unload，即使中间发生异常也会安全触发卸载
    result = await Runner.run(agent, input="你好")
    print(f"\n输出: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
```

**要点**：
- 生命周期钩子在每次 `Runner.run()` 开始前和结束时自动执行。
- 利用 `skill.context` 安全存储临时资源，防止资源泄露。

---

## 示例 11：编排增强 — 循环退出条件与并行提前终止

处理复杂任务时，编排器（Orchestrators）提供了更高级的控制流：
1. **LoopAgent 的动态退出**：通过 `loop_condition` 在每一轮动态判断是否继续。
2. **ParallelAgent 的提前终止**：通过 `early_exit=True`，当任一分支发现重大问题（`escalate`）时，立即取消其他正在执行的分支。

```python
import asyncio
from agentkit import Agent, Runner, LoopAgent, ParallelAgent
from agentkit.runner.events import Event
from agentkit.agents.base_agent import BaseAgent

# --- 1. LoopAgent 增强：动态退出条件 ---
def check_status(ctx, state):
    iteration = state["iteration"]
    if iteration >= 2:
        print(f"[Loop] 自定义条件达成，将在第 {iteration} 轮终止循环。")
        return False  # 返回 False 终止循环
    return True

loop_agent = LoopAgent(
    name="review-loop",
    max_iterations=5,
    loop_condition=check_status,
    sub_agents=[
        Agent(name="coder", instructions="直接说 '我写好代码了'", model="ollama/qwen3.5:cloud"),
    ]
)

# --- 2. ParallelAgent 增强：提前终止 (early_exit) ---
# 为了演示，我们手写两个底层 Agent：一个耗时慢，一个立刻报错(escalate)
class SlowAgent(BaseAgent):
    async def _run_impl(self, ctx):
        print("[Parallel] 慢任务开始，预计耗时 3 秒...")
        try:
            await asyncio.sleep(3)
            yield Event(agent=self.name, type="final_output", data="慢任务完成")
        except asyncio.CancelledError:
            print("[Parallel] 慢任务被提前取消 (Cancelled)！")

class FastEscalateAgent(BaseAgent):
    async def _run_impl(self, ctx):
        print("[Parallel] 检查任务发现致命错误，立即 escalate！")
        yield Event(agent=self.name, type="escalate", data="发现安全漏洞")

parallel_agent = ParallelAgent(
    name="multi-task",
    early_exit=True, # 开启此项，任一分支 escalate 都会取消其他分支
    sub_agents=[SlowAgent(name="slow"), FastEscalateAgent(name="fast")]
)

async def main():
    print("=== 演示 LoopAgent (自定义条件) ===")
    await Runner.run(loop_agent, input="开始工作")
    
    print("\n=== 演示 ParallelAgent (提前取消) ===")
    async for event in Runner.run_streamed(parallel_agent, input="开始并行任务"):
        if event.type == "parallel_early_exit":
            print(f"✅ 触发提前终止事件: {event.data['reason']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 示例 12：RunContext 序列化与共享状态

`RunContext` 记录了单次对话的完整上下文。通过内置的序列化协议，你可以将其轻松保存与恢复，甚至支持自定义 `shared_context` 的序列化。

```python
import asyncio
from agentkit.runner.context import RunContext

class MySharedState:
    def __init__(self, user_role: str):
        self.user_role = user_role

    def __ak_serialize__(self) -> dict:
        return {"user_role": self.user_role}

    @classmethod
    def __ak_deserialize__(cls, data: dict) -> "MySharedState":
        return cls(user_role=data.get("user_role", "guest"))

# 1. 序列化
ctx = RunContext(
    input="你好",
    shared_context=MySharedState(user_role="admin")
)
json_data = ctx.to_json()
print("序列化结果:", json_data)

# 2. 反序列化
restored_ctx = RunContext.from_json(json_data, shared_context_cls=MySharedState)
print("恢复的角色:", restored_ctx.shared_context.user_role)
```

---

## 示例 13：Human-in-the-loop 与断点续跑

AgentKit 原生支持 Human-in-the-loop (HITL) 机制，允许任务在需要人工介入时挂起（Suspend），并保存当前执行快照（Checkpoint），后续再恢复（Resume）执行。

```python
import asyncio
from agentkit import Agent, Runner
from agentkit.tools.base_tool import request_human_input
from agentkit.tools.function_tool import FunctionTool
from agentkit.runner.context_store import InMemoryContextStore
from agentkit.runner.events import EventType

def confirm_action(action: str) -> str:
    """在执行敏感操作前请求人工确认"""
    # 抛出异常中断执行，Runner 将其转为挂起事件
    request_human_input(f"即将执行: {action}，请确认(yes/no)")

confirm_tool = FunctionTool.from_function(confirm_action)
agent = Agent(name="ops", instructions="...", tools=[confirm_tool])
store = InMemoryContextStore()
session_id = "session_001"

async def main():
    # 第 1 阶段：启动并挂起
    async for event in Runner.run_with_checkpoint(
        agent, input="重启数据库", session_id=session_id, context_store=store
    ):
        if event.type == EventType.SUSPEND_REQUESTED:
            print("🚨 任务已挂起，等待人工输入...")
    
    # 此时进程可完全退出，状态已持久化
    
    # 第 2 阶段：恢复执行
    async for event in Runner.resume(
        agent, session_id=session_id, user_input="yes", context_store=store
    ):
        if event.type == EventType.FINAL_OUTPUT:
            print("最终结果:", event.data)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 示例 14：事件协议标准化与强类型校验

AgentKit 提供了标准化的 `EventType` 枚举以及强类型的 `validate_data` 校验方法，保证你在处理复杂事件流时安全可靠。

```python
import asyncio
from agentkit import Agent, Runner
from agentkit.runner.events import EventType
from pydantic import BaseModel

class ToolResultSchema(BaseModel):
    tool: str
    result: str

agent = Agent(name="math", instructions="计算 10+20")

async def main():
    async for event in Runner.run_streamed(agent, input="开始"):
        if event.type == EventType.TOOL_RESULT:
            try:
                # 将弱类型的字典强转为 Pydantic 模型
                data = event.validate_data(ToolResultSchema)
                print(f"✅ 工具 {data.tool} 执行成功，结果: {data.result}")
            except ValueError as e:
                print(f"❌ 数据格式校验失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 性能提示

当你感觉 Agent 响应较慢时，可以尝试以下优化：

### Thinking 模式

qwen3.5 等模型支持「深度思考」。OllamaAdapter **默认开启** thinking，可按需关闭：

```python
from agentkit.llm.registry import LLMRegistry

# 默认开启 thinking
llm = LLMRegistry.create("ollama/qwen3.5:cloud")

# 关闭 thinking（纯对话场景可能更快，但工具调用场景 cloud 模型可能反而更慢）
llm.config.extra_params["think"] = False
agent = Agent(model=llm, instructions="你是助手")
```

> ⚠️ cloud 模型 thinking 本身很快，关闭后效果因场景而异，建议先测试。

### 启用缓存

LLM 响应缓存**默认已开启**，对相同问题直接返回缓存结果。缓存绑定 Agent 实例，不同 Agent 之间互不影响。

```python
# 默认已开启，无需额外配置
agent = Agent(model="ollama/qwen3.5:cloud", ...)

# 需要关闭时：
agent = Agent(model="ollama/qwen3.5:cloud", enable_cache=False, ...)
```

> ⚠️ 仅缓存纯文本回复，不缓存工具调用响应（因为工具结果可能变化）。

### 记忆写入模式

```python
# 默认：异步写入（不阻塞返回，Web 服务推荐）
agent = Agent(memory=my_memory, memory_async_write=True, ...)

# 同步写入（等写完再返回，多轮串行对话推荐）
agent = Agent(memory=my_memory, memory_async_write=False, ...)
```

> ⚠️ 异步模式下，下一轮对话可能读不到上一轮刚存的记忆。多轮串行对话建议设为 `False`。

更多细节请参考 [Architecture.md — 性能优化](Architecture.md#性能优化)。

---

## 使用不同的 LLM

只需修改 `model` 参数即可切换 LLM，无需改动其他代码：

```python
# 本地 Ollama
agent = Agent(model="ollama/qwen3.5:cloud", ...)

# OpenAI
agent = Agent(model="gpt-4o", ...)

# Anthropic Claude
agent = Agent(model="claude-sonnet-4-20250514", ...)

# Google Gemini
agent = Agent(model="gemini-2.5-flash", ...)

# 通义千问 / 智谱 / 百川 / Azure
agent = Agent(model="deepseek/deepseek-chat", ...)
agent = Agent(model="qwen/qwen-max", ...)
agent = Agent(model="zhipu/glm-4", ...)
agent = Agent(model="baichuan/baichuan2-turbo", ...)
agent = Agent(model="azure/your-deployment", ...)
```

### 精细配置

```python
from agentkit import LLMConfig

agent = Agent(
    model=LLMConfig(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=4096,
        fallback_models=["gpt-4o-mini"],  # 失败时自动降级
    ),
    ...
)
```

### 设置全局默认模型

```python
from agentkit import LLMRegistry

LLMRegistry.set_default("ollama/qwen3.5:cloud")

# 之后创建的 Agent 如果不指定 model，将使用这个默认模型
agent = Agent(name="assistant", instructions="...")
```

---

## 完整示例源码

以上所有示例均提供了可直接运行的独立源码文件，分为两个版本：

### 📁 `examples/standard/` — 标准版（使用 OpenAI GPT-4o，需要 API Key）

| 文件 | 对应示例 |
|------|---------|
| [`01_basic_chat.py`](../examples/standard/01_basic_chat.py) | 示例 1：最简 Agent |
| [`02_tool_calling.py`](../examples/standard/02_tool_calling.py) | 示例 2：工具调用 |
| [`03_skill_usage.py`](../examples/standard/03_skill_usage.py) | 示例 3：Skill 使用 |
| [`04_multi_agent.py`](../examples/standard/04_multi_agent.py) | 示例 4：多 Agent 协作 |
| [`05_guardrail.py`](../examples/standard/05_guardrail.py) | 示例 5：安全护栏 |
| [`06_orchestration.py`](../examples/standard/06_orchestration.py) | 示例 6：编排 Agent |
| [`07_sync_async_stream.py`](../examples/standard/07_sync_async_stream.py) | 示例 7：同步/异步/流式运行 |
| [`08a_memory_simple_provider.py`](../examples/standard/08a_memory_simple_provider.py) | 示例 8A：记忆系统（SimpleMemory） |
| [`08b_memory_mem0_provider.py`](../examples/standard/08b_memory_mem0_provider.py) | 示例 8B：记忆系统（Mem0Provider） |
| [`08c_memory_file_provider.py`](../examples/standard/08c_memory_file_provider.py) | 示例 8C：记忆系统（文件持久化） |
| [`09a_structured_data_sql.py`](../examples/standard/09a_structured_data_sql.py) | 示例 9A：关系型数据库 |
| [`09b_structured_data_graph.py`](../examples/standard/09b_structured_data_graph.py) | 示例 9B：图数据库 |
| [`09c_nebula_graph_tool.py`](../examples/standard/09c_nebula_graph_tool.py) | 示例 9C：NebulaGraphTool 最小可执行示例 |
| [`10_skill_lifecycle.py`](../examples/standard/10_skill_lifecycle.py) | 示例 10：Skill 生命周期 |
| [`11_orchestration_enhancement.py`](../examples/standard/11_orchestration_enhancement.py) | 示例 11：编排增强 |
| [`12_run_context_serialization.py`](../examples/standard/12_run_context_serialization.py) | 示例 12：RunContext 序列化与共享状态 |
| [`13_human_in_the_loop.py`](../examples/standard/13_human_in_the_loop.py) | 示例 13：Human-in-the-loop 与断点续跑 |
| [`14_event_standardization.py`](../examples/standard/14_event_standardization.py) | 示例 14：事件协议标准化与强类型校验 |
| [`15_multi_tenant_isolation.py`](../examples/standard/15_multi_tenant_isolation.py) | 示例 15：多租户隔离 |
| [`16_lifecycle_hooks.py`](../examples/standard/16_lifecycle_hooks.py) | 示例 16：生命周期 Hooks 与 Callbacks |
| [`17_checkpoint_handoff_resume.py`](../examples/standard/17_checkpoint_handoff_resume.py) | 示例 17：Checkpoint 深度恢复（Handoff + Resume） |
| [`18_model_cosplay.py`](../examples/standard/18_model_cosplay.py) | 示例 18：ModelCosplay（运行时改写预设模型） |

### 📁 `examples/ollama/` — Ollama 本地版（无需 API Key，完全本地运行）

| 文件 | 对应示例 |
|------|---------|
| [`01_basic_chat.py`](../examples/ollama/01_basic_chat.py) | 示例 1：最简 Agent |
| [`02_tool_calling.py`](../examples/ollama/02_tool_calling.py) | 示例 2：工具调用 |
| [`03_skill_usage.py`](../examples/ollama/03_skill_usage.py) | 示例 3：Skill 使用 |
| [`04_multi_agent.py`](../examples/ollama/04_multi_agent.py) | 示例 4：多 Agent 协作 |
| [`05_guardrail.py`](../examples/ollama/05_guardrail.py) | 示例 5：安全护栏 |
| [`06_orchestration.py`](../examples/ollama/06_orchestration.py) | 示例 6：编排 Agent |
| [`07_sync_async_stream.py`](../examples/ollama/07_sync_async_stream.py) | 示例 7：同步/异步/流式运行 |
| [`08a_memory_simple_provider.py`](../examples/ollama/08a_memory_simple_provider.py) | 示例 8A：记忆系统（SimpleMemory） |
| [`08b_memory_mem0_provider.py`](../examples/ollama/08b_memory_mem0_provider.py) | 示例 8B：记忆系统（Mem0Provider） |
| [`08c_memory_file_provider.py`](../examples/ollama/08c_memory_file_provider.py) | 示例 8C：记忆系统（文件持久化） |
| [`09a_structured_data_sql.py`](../examples/ollama/09a_structured_data_sql.py) | 示例 9A：关系型数据库 |
| [`09b_structured_data_graph.py`](../examples/ollama/09b_structured_data_graph.py) | 示例 9B：图数据库 |
| [`09c_nebula_graph_tool.py`](../examples/ollama/09c_nebula_graph_tool.py) | 示例 9C：NebulaGraphTool 最小可执行示例 |
| [`10_skill_lifecycle.py`](../examples/ollama/10_skill_lifecycle.py) | 示例 10：Skill 生命周期 |
| [`11_orchestration_enhancement.py`](../examples/ollama/11_orchestration_enhancement.py) | 示例 11：编排增强 |
| [`12_run_context_serialization.py`](../examples/ollama/12_run_context_serialization.py) | 示例 12：RunContext 序列化与共享状态 |
| [`13_human_in_the_loop.py`](../examples/ollama/13_human_in_the_loop.py) | 示例 13：Human-in-the-loop 与断点续跑 |
| [`14_event_standardization.py`](../examples/ollama/14_event_standardization.py) | 示例 14：事件协议标准化与强类型校验 |
| [`15_multi_tenant_isolation.py`](../examples/ollama/15_multi_tenant_isolation.py) | 示例 15：多租户隔离 |
| [`16_lifecycle_hooks.py`](../examples/ollama/16_lifecycle_hooks.py) | 示例 16：生命周期 Hooks 与 Callbacks |
| [`17_checkpoint_handoff_resume.py`](../examples/ollama/17_checkpoint_handoff_resume.py) | 示例 17：Checkpoint 深度恢复（Handoff + Resume） |
| [`18_model_cosplay.py`](../examples/ollama/18_model_cosplay.py) | 示例 18：ModelCosplay（运行时改写预设模型） |

---

### 15. 多租户隔离 (Multi-Tenant Isolation)

AgentKit 从底层框架级别支持多租户与多会话隔离。通过在 `Runner.run` 中传入 `user_id` 和 `session_id`：

1. **记忆分桶**：Memory 系统（如 Mem0Provider）会自动将 `user_id` 作为分桶键，实现跨用户记忆绝对隔离。
2. **状态隔离**：Skill 与 Tool 的上下文（Context）通过 `RunContext.state` 按 `session_id` 独立管理。
3. **资源释放监控**：会话结束后，框架自动调用所有 Skill 的 `on_unload` 清理资源，并输出包含释放耗时的监控日志。

```python
from agentkit.agents.agent import Agent
from agentkit.runner.runner import Runner

# 假设已经配置好了 Memory 和相关的 Skill
agent = Agent(name="TenantAgent", memory=memory_provider)

# User A 的请求
await Runner.run(agent, input="记住我是 Alice", user_id="user_A_123")

# User B 的请求
result = await Runner.run(agent, input="我叫什么？", user_id="user_B_456")
print(result.final_output)  # User B 不会知道 Alice 的名字

# 通过日志可以看到资源被自动释放与耗时
```

### 16. 生命周期 Hooks 与 Callbacks

如果你需要对 Agent 的执行过程进行 APM 监控、数据脱敏、请求改写或审计，可以使用生命周期钩子：

```python
async def before_model(ctx, instructions, tools):
    print("准备调用 LLM，可以在这里动态修改 Prompt 或注入额外系统信息")
    # instructions += "\n[系统提示: 今天是周五]"
    # 如果返回非 None 值，将直接覆盖 LLM 的调用结果

async def after_model(ctx, response):
    print("收到 LLM 响应，准备对其进行脱敏或追加内容")
    if response.content:
        response.content += "\n[安全审计系统: 本回答由 AI 生成]"
    return response

agent = Agent(
    name="HookAgent",
    instructions="你是一个安全助手",
    model="gpt-4o-mini",
    before_model_callback=before_model,
    after_model_callback=after_model,
    # 其他钩子: before_agent, after_agent, before_tool, after_tool, before_handoff, after_handoff, on_error
    fail_fast_on_hook_error=False # 如果 Hook 发生异常，仅记录 Event 而不中断主流程
)
```

### 17. Checkpoint 深度恢复（Handoff 后挂起与原路径恢复）

`Runner.run_with_checkpoint` 与 `Runner.resume` 现在会在挂起时保存执行指针（轮次、当前 Agent、agent_path），恢复时按路径回到正确的 Agent 节点继续运行，避免复杂编排下回到入口 Agent 重跑。

```python
from agentkit.runner.context_store import InMemoryContextStore
from agentkit.runner.runner import Runner

store = InMemoryContextStore()
session_id = "demo-handoff-checkpoint-001"

# 阶段 1：触发 handoff 后挂起（保存执行指针）
async for event in Runner.run_with_checkpoint(
    root_agent,
    input="请审批部署任务",
    session_id=session_id,
    context_store=store,
    max_turns=5,
):
    print(event.type, event.agent, event.data)

# 阶段 2：恢复（按 agent_path 回到挂起点继续）
async for event in Runner.resume(
    root_agent,
    session_id=session_id,
    user_input="approve",
    context_store=store,
):
    print(event.type, event.agent, event.data)
```

运行文件：
- `examples/standard/17_checkpoint_handoff_resume.py`
- `examples/ollama/17_checkpoint_handoff_resume.py`

### 18. ModelCosplay（运行时改写预设模型）

`ModelCosplay` 是 Agent 的底层能力开关，默认关闭：

1. 关闭时：如果 Agent 已经预设 `model`，实例化时不允许覆盖。
2. 开启时：允许实例化覆盖预设模型。
3. 开启时：允许运行时通过 `apply_model_cosplay(...)` 切换模型。

```python
from typing import AsyncGenerator
from agentkit import Agent, Runner
from agentkit.runner.events import Event, EventType

class ModelEchoAgent(Agent):
    async def _run_impl(self, ctx) -> AsyncGenerator[Event, None]:
        # 为了演示，不调用真实 LLM，只返回当前 model
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=f"active_model={self.model}")

class LockedAgent(ModelEchoAgent):
    model = "ollama/qwen3.5:cloud"
    model_cosplay_enabled = False

class CosplayAgent(ModelEchoAgent):
    model = "ollama/qwen3.5:cloud"
    model_cosplay_enabled = True

# 1) 默认关闭：覆盖失败
try:
    LockedAgent(name="locked", model="ollama/llama3:8b")
except ValueError as e:
    print(e)

# 2) 开启后：实例化覆盖成功
agent = CosplayAgent(name="cosplay", model="ollama/llama3:8b")
print(Runner.run_sync(agent, input="show").final_output)

# 3) 开启后：运行时覆盖成功
agent.apply_model_cosplay("ollama/qwen2.5:7b")
print(Runner.run_sync(agent, input="show").final_output)
```

运行文件：
- `examples/standard/18_model_cosplay.py`
- `examples/ollama/18_model_cosplay.py`

## 下一步

- 📐 阅读 **[Architecture.md](Architecture.md)** 了解框架的六层架构设计
- 📚 阅读 **[Reference.md](Reference.md)** 查看完整的 API 参考手册
- 🔬 查看 `examples/` 目录中的更多示例代码
