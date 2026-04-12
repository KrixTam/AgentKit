# AgentKit

> Python 原生的 Agent 开发框架，内置一等公民级别的 Skill 支持和自研多模型适配层。

[![Python](https://img.shields.io/badge/Python-≥3.11-blue.svg)](https://python.org)
[![Version](https://img.shields.io/badge/Version-0.3.0-green.svg)]()
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)]()

---

## ✨ 特性一览

| 特性 | 说明 |
|------|------|
| **Skill 一等公民** | `skills=[...]` 与 `tools=[...]` 并列，三级渐进式加载（L1/L2/L3）节省 token |
| **自研多模型适配** | OpenAI / Anthropic / Google Gemini / Ollama / 国内模型（DeepSeek、通义千问、智谱…），前缀自动路由 |
| **双协作模式** | Handoff（控制权转移）+ as_tool（Agent 当工具调用），灵活覆盖所有协作场景 |
| **编排 Agent** | SequentialAgent / ParallelAgent / LoopAgent，组合出任意复杂的工作流 |
| **@function_tool** | 一行装饰器把 Python 函数变成 LLM 工具，自动推断 JSON Schema |
| **安全内置** | Input/Output 双向 Guardrail + 三层权限控制 + 三级沙箱执行 |
| **记忆系统** | Mem0 集成，跨会话长期记忆 |
| **6 个回调点** | before/after × agent/model/tool，任何环节可拦截定制 |

---

## 📦 安装

```bash
# 基础安装
pip install pydantic>=2.0

# 按需安装 LLM 适配器
pip install openai>=1.0.0          # OpenAI + 国内兼容厂商
pip install anthropic>=0.30.0      # Anthropic Claude
pip install google-genai>=1.0.0    # Google Gemini
pip install aiohttp>=3.9.0         # Ollama 本地模型

# 可选
pip install mem0ai>=0.1.0          # 记忆系统
pip install docker>=7.0.0          # Docker 沙箱
```

---

## 🚀 30 秒快速开始

```python
from agentkit import Agent, Runner, function_tool

# 1. 定义工具
@function_tool
def calculate(expression: str) -> str:
    """计算数学表达式"""
    return str(eval(expression))

# 2. 创建 Agent
agent = Agent(
    name="assistant",
    instructions="你是一个有帮助的中文助手。需要计算时请使用工具。",
    model="ollama/qwen3.5:cloud",   # 或 "gpt-4o"、"claude-sonnet-4-20250514"、"deepseek/deepseek-chat"
    tools=[calculate],
)

# 3. 运行
result = Runner.run_sync(agent, input="请计算 (15 + 27) * 3")
print(result.final_output)
```

---

## 📖 文档目录

| 文档 | 说明 |
|------|------|
| **[QuickStart.md](docs/QuickStart.md)** | 详细入门教程，包含 6 个从简到繁的完整示例 |
| **[Architecture.md](docs/Architecture.md)** | 架构设计说明：六层分层、设计原则、核心流程 |
| **[Reference.md](docs/Reference.md)** | 完整 API 参考手册：所有类、方法、参数说明 |

---

## 🤖 支持的 LLM

使用模型标识字符串即可自动路由到对应适配器，**零配置**：

| 模型标识 | 适配器 | 示例 |
|---------|--------|------|
| `gpt-4o`、`gpt-4o-mini`、`o1`、`o3` | OpenAIAdapter | `model="gpt-4o"` |
| `claude-sonnet-4-20250514`、`claude-opus-4-20250514` | AnthropicAdapter | `model="claude-sonnet-4-20250514"` |
| `gemini-2.5-pro`、`gemini-2.5-flash` | GoogleAdapter | `model="gemini-2.5-pro"` |
| `ollama/qwen3.5:cloud`、`ollama/qwen3.5:4b` | OllamaAdapter | `model="ollama/qwen3.5:cloud"` |
| `deepseek/deepseek-chat` | OpenAICompatibleAdapter | `model="deepseek/deepseek-chat"` |
| `qwen/qwen-max` | OpenAICompatibleAdapter | `model="qwen/qwen-max"` |
| `zhipu/glm-4` | OpenAICompatibleAdapter | `model="zhipu/glm-4"` |

---

## 🏗️ 项目结构

```
agentkit/
├── agents/          # Agent 层（BaseAgent + Agent + 编排器）
├── tools/           # Tool 层（BaseTool + @function_tool + SkillToolset）
├── skills/          # Skill 层（数据模型 + 加载器 + 注册中心）
├── llm/             # LLM 适配层（5 个适配器 + Registry + 中间件）
├── runner/          # Runner 层（核心循环 + 上下文 + 事件）
├── safety/          # 安全层（Guardrail + 权限控制）
├── memory/          # 记忆系统（Mem0 集成）
├── utils/           # 工具函数（JSON Schema 生成）
├── examples/        # 使用示例
└── docs/            # 文档
```

---

## 📄 许可证

MIT License
