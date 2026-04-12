# 标准示例（需要 API Key）

使用 OpenAI GPT-4o 模型的示例。运行前请设置：

```bash
export OPENAI_API_KEY="sk-..."
pip install openai>=1.0.0
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
| `07_sync_async_stream.py` | 三种运行方式 — 同步/异步/流式 | 同步与异步 |
| `08_memory.py` | 记忆系统 — 跨会话长期记忆 | 记忆系统 |

## 运行

```bash
python examples/standard/01_basic_chat.py
python examples/standard/02_tool_calling.py
# ... 以此类推
```

> 💡 如果没有 OpenAI API Key，请使用 `examples/ollama/` 目录中的 Ollama 本地版示例。
