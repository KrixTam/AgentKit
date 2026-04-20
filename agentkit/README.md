# AgentKit

**Python 原生 Agent 框架，内置一等公民 Skill 支持与多 LLM 适配器。**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 特性

- 🤖 **声明式 Agent** — 零继承配置，支持 Handoff 转介 + as_tool 委派两种协作模式
- 📚 **一等公民 Skill** — 三级渐进式加载（L1 元数据 → L2 指令 → L3 资源），按需加载省 token
- 🔧 **灵活工具系统** — `@function_tool` 装饰器自动推断 JSON Schema
- 🧠 **多 LLM 适配器** — 自研统一适配层，5 个适配器覆盖主流 LLM（含 OpenAI Compatible）
- 🛡️ **内置安全** — Guardrail 护栏 + 权限控制；`run_skill_script` 当前为占位执行（SandboxExecutor 预留扩展）
- 🎭 **编排 Agent** — Sequential / Parallel / Loop 三种模式
- 💾 **记忆系统** — 可选集成 Mem0，支持自定义记忆提供者
- ⚡ **全异步设计与 Hooks** — 底层全面采用 `asyncio`，流式响应（Streaming）、事件驱动（Event-Driven）、断点续跑机制（Checkpoint/Resume）。提供细粒度的 生命周期 Hooks，支持改写请求与结果。
- 🏢 **多租户数据隔离** — 框架级支持 `user_id` / `session_id` 贯穿，Memory 默认分桶，Session 结束自动释放资源。
- 🔗 **与大模型平台解耦** — 内置多模型支持，轻松对接 Ollama 等本地模型。

## 🚀 安装

```bash
# 基础安装
pip install ni.agentkit

# 如果需要 OpenAI / DeepSeek / 通义千问等
pip install "ni.agentkit[openai]"
pip install "ni.agentkit[anthropic]"
pip install "ni.agentkit[google]"
pip install "ni.agentkit[memory]"
pip install "ni.agentkit[docker]"
pip install "ni.agentkit[all]"
```

## ⚡ 30 秒快速开始

```python
from agentkit import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """获取天气"""
    return f"{city}：晴，25°C"

agent = Agent(
    name="assistant",
    instructions="你是一个有帮助的中文助手。",
    model="ollama/qwen3.5:cloud",
    tools=[get_weather],
)

result = Runner.run_sync(agent, input="北京今天天气如何？")
print(result.final_output)
```

## 📚 文档

安装后查看文档：

```bash
# 命令行方式
agentkit-docs

# Python 方式
import agentkit
print(agentkit.get_docs_dir())     # 文档目录路径
print(agentkit.get_examples_dir()) # 示例目录路径
```

| 文档 | 说明 |
|------|------|
| [README](docs/README.md) | 项目概述与特性 |
| [QuickStart](docs/QuickStart.md) | 18 组渐进式入门示例（含 9A/9B） |
| [Architecture](docs/Architecture.md) | 六层架构设计说明 |
| [Reference](docs/Reference.md) | 完整 API 参考手册 |

## 🧪 示例

安装包内含 36 个可运行示例（标准版 × 18 + Ollama 本地版 × 18）：

```bash
# Ollama 本地版（无需 API Key）
python -c "import agentkit; print(agentkit.get_examples_dir())"
# 然后运行对应目录下的示例文件

# 或者直接运行示例文件：
python "$(python -c "import agentkit, os; print(os.path.join(agentkit.get_examples_dir(), 'ollama', '01_basic_chat.py'))")"
```

## 🔌 支持的 LLM

| 模型 | 适配器 | 用法 |
|------|--------|------|
| GPT-4o / o1 / o3 / o4 | OpenAIAdapter | `model="gpt-4o"` |
| Claude Opus/Sonnet/Haiku | AnthropicAdapter | `model="claude-sonnet-4-20250514"` |
| Gemini 2.5 / 3 | GoogleAdapter | `model="gemini-2.5-pro"` |
| 通义千问/智谱/DeepSeek/Moonshot/百川/Azure | OpenAICompatibleAdapter | `model="deepseek/deepseek-chat"` |
| Ollama 本地模型 | OllamaAdapter | `model="ollama/qwen3.5:cloud"` |

## 🔨 构建打包

```bash
./build.sh          # 构建 wheel + sdist
./build.sh clean    # 清理构建产物
./build.sh test     # 在隔离环境中安装并验证
./build.sh all      # 清理 + 构建 + 验证（推荐）
```

构建产物输出到 `dist/` 目录：

```bash
dist/
├── ni_agentkit-0.6.0-py3-none-any.whl   # pip install 用这个
└── ni_agentkit-0.6.0.tar.gz             # 源码分发
```

## 📄 License

MIT
