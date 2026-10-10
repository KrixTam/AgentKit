# AgentKit

> Python 原生的 Agent 开发框架，内置一等公民级别的 Skill 支持和自研多模型适配层。

[![Python](https://img.shields.io/badge/Python-≥3.11-blue.svg)](https://python.org)
[![Version](https://img.shields.io/badge/Version-0.8.1-green.svg)]()
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)]()

---

## ✨ 特性一览

| 特性 | 说明 |
|------|------|
| **Skill 一等公民** | `skills=[...]` 与 `tools=[...]` 并列，三级渐进式加载（L1/L2/L3）节省 token。支持资源生命周期管理（on_load/on_unload 钩子） |
| **自研多模型适配** | OpenAI / Anthropic / Google Gemini / Ollama / 国内模型（DeepSeek、通义千问、智谱…），前缀自动路由 |
| **双协作模式** | Handoff（控制权转移）+ as_tool（Agent 当工具调用），灵活覆盖所有协作场景 |
| **编排 Agent** | SequentialAgent / ParallelAgent / LoopAgent，组合出任意复杂的工作流。支持 Loop 动态退出条件与 Parallel 提前取消增强 |
| **@function_tool** | 一行装饰器把 Python 函数变成 LLM 工具，自动推断 JSON Schema。内建 `StructuredDataTool` 防止数据库注入 |
| **图数据统一接口层** | 提供 `GraphAdapter + GraphRepository + GraphQueryTool`，开发/测试可切换 `networkx/litegraph`，生产可切换 `nebula` |
| **SimpleRAGAgent / HybridRAGAgent** | 同时提供轻量入门版 RAG（V1）与增强版混合检索 RAG（V2）；V2 默认采用 BM25 + Chroma 向量检索 + RRF + Reranker |
| **安全内置** | Input/Output 双向 Guardrail + 三层权限控制；`run_skill_script` 当前为占位执行（SandboxExecutor 预留扩展） |
| **记忆系统** | Mem0 集成 + 自定义记忆提供者；`SimpleRAGAgent` 与 `HybridRAGAgent` 默认均可接入 `SQLiteMemoryProvider` |
| **9 个回调点** | before/after × agent/model/tool/handoff + error，任何环节可拦截定制 |

---

## 📦 安装

```bash
# 基础安装
pip install ni.agentkit

# 按需安装额外依赖
pip install "ni.agentkit[openai]"    # OpenAI + 国内兼容厂商
pip install "ni.agentkit[anthropic]" # Anthropic Claude
pip install "ni.agentkit[google]"    # Google Gemini
pip install "ni.agentkit[memory]"    # 记忆系统 (mem0)
pip install "ni.agentkit[pdf]"       # PDF 知识库解析（可选）
pip install "ni.agentkit[rag]"       # HybridRAGAgent（ChromaDB）
pip install "ni.agentkit[rerank]"    # 本地 rerank sidecar
pip install "ni.agentkit[all]"       # 安装所有可选依赖
```

安装完成后，如果你想快速生成一个可直接运行的 `HybridRAGAgent` 工作目录，可执行：

```bash
agentkit-hybrid-rag-init
```

该命令会通过交互式向导生成 `.env`、`create_agent.py`、`start_rerank_server.py`、`chat.py`、`README.md` 等文件，适合本地快速体验和二次修改。知识库目录默认使用 `knowledge_base/`，也支持在向导中指定自定义相对路径或绝对路径；生成后的 `chat.py` 会打印当前实际使用的知识库目录，`start_rerank_server.py` 可直接启动本地 rerank sidecar。推荐进入工作目录后先执行 `python start_rerank_server.py`，再执行 `python chat.py`。

如果你希望在本地启用 `HybridRAGAgent` 的重排阶段，也可以启动随包提供的 rerank sidecar：

```bash
ollama serve
ollama pull qllama/bge-small-zh-v1.5:f16
ollama pull qllama/bce-reranker-base_v1:f16
pip install "ni.agentkit[rerank]"
agentkit-rerank-server --model qllama/bce-reranker-base_v1:f16
```

如果默认 `qllama/bce-reranker-base_v1:f16` 在当前 Ollama 版本上无法通过 `/api/embed` 提供向量，sidecar 会自动回退到 `qllama/bge-small-zh-v1.5:f16` 继续完成排序，避免整条检索链路中断。

安装完成后，也可以通过以下入口快速查看文档、示例与工作目录脚手架：

```bash
agentkit-docs
agentkit-hybrid-rag-init
agentkit-rerank-server --help
```

```python
import agentkit

print(agentkit.get_docs_dir())      # 文档目录
print(agentkit.get_examples_dir())  # 示例目录
```

---

## 🚀 30 秒快速开始

```python
from agentkit import Agent, function_tool

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
result = agent.invoke(input="请计算 (15 + 27) * 3")
print(result.final_output)
```

---

## 📖 文档目录

| 文档 | 说明 |
|------|------|
| **[QuickStart.md](QuickStart.md)** | 详细入门教程，包含从简到繁的完整示例（含 SimpleRAGAgent V1 / HybridRAGAgent V2） |
| **[Architecture.md](Architecture.md)** | 架构设计说明：六层分层、设计原则、核心流程 |
| **[Reference.md](Reference.md)** | 完整 API 参考手册：所有类、方法、参数说明 |

---

## 🤖 支持的 LLM

使用模型标识字符串即可自动路由到对应适配器，**零配置**：

| 模型标识 | 适配器 | 示例 |
|---------|--------|------|
| `gpt-4o`、`gpt-4o-mini`、`o1`、`o3`、`o4` | OpenAIAdapter | `model="gpt-4o"` |
| `claude-sonnet-4-20250514`、`claude-opus-4-20250514` | AnthropicAdapter | `model="claude-sonnet-4-20250514"` |
| `gemini-2.5-pro`、`gemini-2.5-flash` | GoogleAdapter | `model="gemini-2.5-pro"` |
| `ollama/qwen3.5:cloud`、`ollama/qwen3.5:4b` | OllamaAdapter | `model="ollama/qwen3.5:cloud"` |
| `deepseek/deepseek-chat` | OpenAICompatibleAdapter | `model="deepseek/deepseek-chat"` |
| `qwen/qwen-max` | OpenAICompatibleAdapter | `model="qwen/qwen-max"` |
| `zhipu/glm-4` | OpenAICompatibleAdapter | `model="zhipu/glm-4"` |
| `baichuan/baichuan2-turbo` | OpenAICompatibleAdapter | `model="baichuan/baichuan2-turbo"` |
| `azure/your-deployment` | OpenAICompatibleAdapter | `model="azure/your-deployment"` |

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
├── ni_agentkit-0.8.1-py3-none-any.whl
└── ni_agentkit-0.8.1.tar.gz
```

---

## 📄 许可证

MIT License
