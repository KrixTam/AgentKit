# Ollama 本地示例（无需 API Key）

使用本地 Ollama + qwen3.5:cloud 模型的示例。**无需任何 API Key，完全本地运行。**

## 环境准备

```bash
# 1. 安装 Ollama: https://ollama.com
# 2. 拉取模型
ollama pull qwen3.5:cloud

# 3. 确认 Ollama 正在运行
curl http://localhost:11434/api/tags

# 4. 安装 Python 依赖
pip install ni.agentkit
```

## 示例列表

| 文件 | 内容 | 对应教程 |
|------|------|---------|
| `01_basic_chat.py` | 最简 Agent — 纯对话 | QuickStart 示例 1 |
| `02_tool_calling.py` | 带工具的 Agent — Function Calling | QuickStart 示例 2 |
| `03_skill_usage.py` | 带 Skill 的 Agent — 领域知识包 | QuickStart 示例 3 |
| `04_multi_agent.py` | 多 Agent 协作 — Handoff 与 as_tool | QuickStart 示例 4 |
| `05_guardrail.py` | 安全护栏 — Guardrail 与权限控制 | QuickStart 示例 5 |
| `06_orchestration.py` | 编排 Agent — 流水线与循环 | QuickStart 示例 6 |
| `07_sync_async_stream.py` | 三种运行方式 — 同步/异步/流式 | QuickStart 示例 7 |
| `08_memory.py` | 记忆系统 — 跨会话长期记忆 | QuickStart 示例 8 |
| `09a_structured_data_sql.py` | 关系型数据库 — 防止 SQL 注入的参数化 Tool | QuickStart 示例 9A |
| `09b_structured_data_graph.py` | 图数据库 — 配合 Mock 运行的 NebulaGraphTool | QuickStart 示例 9B |
| `10_skill_lifecycle.py` | Skill 生命周期 — 管理外部资源连接池 | QuickStart 示例 10 |
| `11_orchestration_enhancement.py` | 编排增强 — 循环退出条件与并行提前终止 | QuickStart 示例 11 |
| `17_checkpoint_handoff_resume.py` | Checkpoint 深度恢复 — Handoff 后挂起并原路径恢复 | 增强示例 |

## 运行

```bash
python examples/ollama/01_basic_chat.py
python examples/ollama/02_tool_calling.py
# ... 以此类推
```

## 更换模型

如果你想使用其他 Ollama 模型，只需修改示例中的 `model` 参数：

```python
# 使用其他模型
agent = Agent(model="ollama/llama3:8b", ...)
agent = Agent(model="ollama/gemma:latest", ...)
agent = Agent(model="ollama/qwen3-vl:8b", ...)
```

> 💡 不同模型的 Function Calling 能力不同。qwen3.5:cloud 已经过验证支持完整的工具调用。
