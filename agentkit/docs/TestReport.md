# AgentKit 示例测试报告

> 测试时间：`2026-04-22`  
> 测试环境：`macOS (Apple Silicon)`  
> 模型：Ollama `qwen3.5:cloud`  
> AgentKit 版本：v0.6.2  
> Thinking 模式：开启（默认）  
> LLM 调用模式：非流式（默认）  
> 缓存：开启（默认）  
> 执行脚本：`examples/test_ollama.py`

---

## 测试结果

| # | 示例 | 文件 | 耗时 | 状态 | 说明 |
|---|------|------|-----:|:----:|------|
| 1 | 基础对话 | `01_basic_chat.py` | 19.23s | ✅ | 运行通过 |
| 2 | 工具调用 | `02_tool_calling.py` | 32.68s | ✅ | 运行通过 |
| 3 | Skill 使用 | `03_skill_usage.py` | 45.97s | ✅ | 运行通过 |
| 4 | 多 Agent 协作 | `04_multi_agent.py` | 58.68s | ✅ | 运行通过 |
| 5 | 安全护栏 | `05_guardrail.py` | 10.72s | ✅ | 运行通过 |
| 6 | 编排 Agent | `06_orchestration.py` | 124.03s | ✅ | 运行通过 |
| 7 | 同步/异步/流式 | `07_sync_async_stream.py` | 24.00s | ✅ | 运行通过 |
| 8 | 记忆系统（综合） | `08_memory.py` | 353.75s | ✅ | 运行通过（本轮最慢） |
| 8A | SimpleMemory | `08a_memory_simple_provider.py` | 20.45s | ✅ | 运行通过 |
| 8B | Mem0Provider | `08b_memory_mem0_provider.py` | 0.24s | ✅ | 未配置 `OPENAI_API_KEY` 时自动跳过 |
| 8C | 文件持久化 Memory | `08c_memory_file_provider.py` | 67.98s | ✅ | 运行通过 |
| 9A | 结构化数据（SQL） | `09a_structured_data_sql.py` | 6.35s | ✅ | 运行通过 |
| 9B | 结构化数据（图） | `09b_structured_data_graph.py` | 9.93s | ✅ | 运行通过 |
| 10 | Skill 生命周期 | `10_skill_lifecycle.py` | 2.51s | ✅ | 运行通过 |
| 11 | 编排增强 | `11_orchestration_enhancement.py` | 251.17s | ✅ | 运行通过 |
| 12 | 序列化协议 | `12_run_context_serialization.py` | 0.32s | ✅ | 运行通过 |
| 13 | Human in the Loop | `13_human_in_the_loop.py` | 36.34s | ✅ | 运行通过 |
| 14 | Event 标准化 | `14_event_standardization.py` | 9.09s | ✅ | 运行通过 |
| 15 | 多租户隔离 | `15_multi_tenant_isolation.py` | 0.28s | ✅ | 运行通过 |
| 16 | 生命周期 Hooks | `16_lifecycle_hooks.py` | 0.26s | ✅ | 运行通过 |
| 17 | Checkpoint + Handoff + Resume | `17_checkpoint_handoff_resume.py` | 0.18s | ✅ | 运行通过（本轮最快） |
| 18 | ModelCosplay | `18_model_cosplay.py` | 0.18s | ✅ | 运行通过 |
| | **合计** | | **1074.34s** | **22/22** | |

## 耗时分析

- **最快示例**：17 Checkpoint + Handoff + Resume（0.18s，与 18 并列）
- **最慢示例**：8 记忆系统（353.75s）
- **耗时集中区间**：涉及多轮推理/记忆写入/编排循环的示例耗时显著更高

## 各示例 LLM 调用次数估算

| # | 示例 | LLM 调用次数 | 说明 |
|---|------|:-----------:|------|
| 1 | 基础对话 | 1 | 单次对话 |
| 2 | 工具调用 | ~6 | 多次工具调用与回复生成 |
| 3 | Skill 使用 | ~9 | load_skill + 工具调用 + 回复 |
| 4 | 多 Agent 协作 | ~8 | as_tool + handoff 链路 |
| 5 | 安全护栏 | ~3 | 拦截与放行混合路径 |
| 6 | 编排 Agent | ~12 | Sequential + Parallel + Loop |
| 7 | 同步/异步/流式 | ~7 | 三种运行模式覆盖 |
| 8 | 记忆系统（综合） | ~10 | 记忆读写与多轮对话 |
| 8A | SimpleMemory | ~2 | 轻量关键词检索 |
| 8B | Mem0Provider | ~0 | 未配置 `OPENAI_API_KEY` 时自动跳过 |
| 8C | 文件持久化 Memory | ~2 | 本地文件读写 + 记忆检索 |
| 9A | 结构化数据（SQL） | ~2 | 参数化查询 + 汇总 |
| 9B | 结构化数据（图） | ~2 | 图查询 + 汇总 |
| 10 | Skill 生命周期 | 1 | 单轮校验 |
| 11 | 编排增强 | ~4 | loop_condition + early_exit |
| 12 | RunContext 序列化 | 0 | 纯本地序列化 |
| 13 | HITL 断点续跑 | ~3 | 挂起 + 恢复 |
| 14 | 事件协议标准化 | 1 | 标准事件输出 |
| 15 | 多租户隔离 | ~3 | 多会话隔离验证 |
| 16 | 生命周期 Hooks | ~2 | Hook 链路验证 |
| 17 | Checkpoint Handoff 恢复 | 0 | 自定义事件流，不依赖 LLM |
| 18 | ModelCosplay | 0 | 仅验证模型改写开关与运行时覆盖逻辑，不调用 LLM |

## 已知问题

| 问题 | 严重程度 | 说明 |
|------|:--------:|------|
| 运行异常 | - | 无，22 个示例全部通过（8B 在无 `OPENAI_API_KEY` 时自动跳过） |

## 运行方式

```bash
# 在 agentkit 目录执行
python examples/test_ollama.py
```
