# AgentKit 快速入门教程

> 本教程将带你从零开始，通过 8 个由简到繁的示例，掌握 AgentKit 的核心用法。

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
- [性能提示](#性能提示)
- [使用不同的 LLM](#使用不同的-llm)
- [下一步](#下一步)

---

## 环境准备

### 1. 安装依赖

```bash
pip install pydantic>=2.0 aiohttp>=3.9.0
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
> Docker 仅在 Skill 脚本沙箱执行的最高安全级别（Level 3）时才需要，大部分场景完全用不到。详见 [Architecture.md](Architecture.md) 中的安全机制说明。

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

review_loop = LoopAgent(
    name="code-review",
    max_iterations=5,
    sub_agents=[
        Agent(name="coder", instructions="根据反馈编写或修改代码", model="ollama/qwen3.5:cloud"),
        Agent(name="reviewer", instructions="审查代码。如果通过则发出 escalate 信号，否则给出修改建议", model="ollama/qwen3.5:cloud"),
    ],
)
```

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

### 无需外部依赖的 SimpleMemory

```python
from agentkit import Agent, Runner, BaseMemoryProvider, Memory

class SimpleMemory(BaseMemoryProvider):
    """轻量内存记忆——适合开发测试"""
    def __init__(self):
        self._store, self._counter = [], 0

    async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
        self._counter += 1
        m = Memory(id=str(self._counter), content=content)
        self._store.append(m)
        return [m]

    async def search(self, query, *, user_id=None, agent_id=None, limit=10):
        # 简单关键词匹配（生产环境用 Mem0 的向量搜索）
        query_words = set(query)
        scored = [(len(query_words & set(m.content)), m) for m in self._store]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [m for s, m in scored[:limit] if s > 0]

    async def get_all(self, *, user_id=None, agent_id=None):
        return list(self._store)

    async def delete(self, memory_id):
        self._store = [m for m in self._store if m.id != memory_id]
        return True

# 给 Agent 配上记忆
memory = SimpleMemory()

agent = Agent(
    name="personal-assistant",
    instructions="你是一个贴心的个人助手。根据记忆来个性化回答。",
    model="ollama/qwen3.5:cloud",
    memory=memory,       # ← 加上这一行
)

# 第 1 轮：告诉偏好
Runner.run_sync(agent, input="我叫小明，我喜欢喝咖啡，讨厌喝茶", user_id="krix")

# 第 2 轮：Agent 会记住偏好，推荐咖啡而不是茶
result = Runner.run_sync(agent, input="帮我推荐一杯饮料", user_id="krix")
print(result.final_output)  # "推荐拿铁！" — 基于记忆推荐
```

**要点**：
- 默认不开启记忆，需要给 `Agent` 传 `memory=...` 参数
- 配好后**不需要写额外代码**——框架自动在对话前检索记忆、对话后存储记忆
- `user_id` 用于多用户隔离

### 生产环境使用 Mem0

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

agent = Agent(memory=memory, ...)     # 替换 SimpleMemory 即可
```

Mem0 相比 SimpleMemory 的优势：**语义搜索**（理解意思而非关键词）、**持久化**（重启不丢失）、**智能提取**（从对话中自动抽取关键信息）。

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
| [`08_memory.py`](../examples/standard/08_memory.py) | 示例 8：记忆系统 |

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
| [`08_memory.py`](../examples/ollama/08_memory.py) | 示例 8：记忆系统 |

---

## 下一步

- 📐 阅读 **[Architecture.md](Architecture.md)** 了解框架的六层架构设计
- 📚 阅读 **[Reference.md](Reference.md)** 查看完整的 API 参考手册
- 🔬 查看 `examples/` 目录中的更多示例代码
