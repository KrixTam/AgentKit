# 标准示例（需要 API Key）

使用 OpenAI GPT-4o 模型的示例。运行前请设置：

```bash
# 基础安装
pip install ni.agentkit

# 如果需要 OpenAI / DeepSeek / 通义千问等
pip install "ni.agentkit[openai]"

export OPENAI_API_KEY="sk-..."
```

## 示例列表

| 文件 | 内容 | 对应教程 |
|------|------|---------|
| `01_basic_chat.py` | 最简 Agent — 纯对话 | QuickStart 示例 1 |
| `02_tool_calling.py` | 带工具的 Agent — Function Calling | QuickStart 示例 2 |
| `03_skill_usage.py` | 带 Skill 的 Agent — 领域知识包 | QuickStart 示例 3 |
| `03b_skill_tools_entry.py` | SKILL.md 的 tools.entry 动态工具注册/发现 | QuickStart 示例 3（方式 C） |
| `04_multi_agent.py` | 多 Agent 协作 — Handoff 与 as_tool | QuickStart 示例 4 |
| `05_guardrail.py` | 安全护栏 — Guardrail 与权限控制 | QuickStart 示例 5 |
| `06_orchestration.py` | 编排 Agent — 流水线与循环 | QuickStart 示例 6 |
| `07_sync_async_stream.py` | 三种运行方式 — 同步/异步/流式 | QuickStart 示例 7 |
| `08_memory.py` | 记忆系统 — 跨会话长期记忆 | QuickStart 示例 8 |
| `09a_structured_data_sql.py` | 关系型数据库 — 防止 SQL 注入的参数化 Tool | QuickStart 示例 9A |
| `09b_structured_data_graph.py` | 图数据库 — 配合 Mock 运行的 NebulaGraphTool | QuickStart 示例 9B |
| `09c_nebula_graph_tool.py` | NebulaGraphTool 最小可执行示例（工具层直调） | QuickStart 示例 9C |
| `10_skill_lifecycle.py` | Skill 生命周期 — 管理外部资源连接池 | QuickStart 示例 10 |
| `11_orchestration_enhancement.py` | 编排增强 — 循环退出条件与并行提前终止 | QuickStart 示例 11 |
| `12_run_context_serialization.py` | RunContext 序列化与共享状态 | QuickStart 示例 12 |
| `13_human_in_the_loop.py` | Human-in-the-loop 与断点续跑 | QuickStart 示例 13 |
| `14_event_standardization.py` | 事件协议标准化与强类型校验 | QuickStart 示例 14 |
| `15_multi_tenant_isolation.py` | 多租户隔离（Multi-Tenant Isolation） | QuickStart 示例 15 |
| `16_lifecycle_hooks.py` | 生命周期 Hooks 与 Callbacks | QuickStart 示例 16 |
| `17_checkpoint_handoff_resume.py` | Checkpoint 深度恢复 — Handoff 后挂起并原路径恢复 | 增强示例 |
| `18_model_cosplay.py` | ModelCosplay — 运行时改写预设模型 | QuickStart 示例 18 |

## 运行

```bash
python examples/standard/01_basic_chat.py
python examples/standard/02_tool_calling.py
# ... 以此类推
```

> 💡 如果没有 OpenAI API Key，请使用 `examples/ollama/` 目录中的 Ollama 本地版示例。
