# AgentKit 示例测试报告

> 测试时间：`2026-10-08`
> 测试环境：`macOS (Apple Silicon)`  
> 模型：`qwen/qwen3.6-flash`（来自 `AGENTKIT_STANDARD_MODEL`）  
> AgentKit 版本：v0.8.1
> Thinking 模式：开启（默认）  
> LLM 调用模式：非流式（默认）  
> 缓存：开启（默认）  
> 执行脚本：`examples/test_standard.py`
> 说明：本报告由 `examples/test_standard.py` 批跑生成，共覆盖 26 个样例；`20_simple_rag_agent.py` 与 `21_hybrid_rag_agent.py` 不在自动批跑范围内。

---

## 测试结果

| # | 示例 | 文件 | 耗时 | 状态 | 说明 |
|---|------|------|-----:|:----:|------|
| 1 | 01_basic_chat | `01_basic_chat.py` | 2.49s | ✅ | 运行通过 |
| 2 | 02_tool_calling | `02_tool_calling.py` | 2.73s | ✅ | 运行通过 |
| 3 | 03_skill_usage | `03_skill_usage.py` | 2.74s | ✅ | 运行通过 |
| 4 | 03b_skill_tools_entry | `03b_skill_tools_entry.py` | 2.44s | ✅ | 运行通过 |
| 5 | 04_multi_agent | `04_multi_agent.py` | 2.48s | ✅ | 运行通过 |
| 6 | 05_guardrail | `05_guardrail.py` | 2.40s | ✅ | 运行通过 |
| 7 | 05_human_in_the_loop | `05_human_in_the_loop.py` | 1.01s | ✅ | 运行通过 |
| 8 | 06_orchestration | `06_orchestration.py` | 2.69s | ✅ | 运行通过 |
| 9 | 07_sync_async_stream | `07_sync_async_stream.py` | 3.54s | ✅ | 运行通过 |
| 10 | 08_memory | `08_memory.py` | 3.50s | ✅ | 运行通过 |
| 11 | 08a_memory_simple_provider | `08a_memory_simple_provider.py` | 2.43s | ✅ | 运行通过 |
| 12 | 08b_memory_mem0_provider | `08b_memory_mem0_provider.py` | 1.02s | ✅ | 运行通过 |
| 13 | 08c_memory_file_provider | `08c_memory_file_provider.py` | 2.46s | ✅ | 运行通过 |
| 14 | 09a_structured_data_sql | `09a_structured_data_sql.py` | 2.19s | ✅ | 运行通过 |
| 15 | 09b_structured_data_graph | `09b_structured_data_graph.py` | 2.27s | ✅ | 运行通过 |
| 16 | 09c_nebula_graph_tool | `09c_nebula_graph_tool.py` | 1.43s | ✅ | 运行通过 |
| 17 | 10_skill_lifecycle | `10_skill_lifecycle.py` | 2.23s | ✅ | 运行通过 |
| 18 | 11_orchestration_enhancement | `11_orchestration_enhancement.py` | 3.21s | ✅ | 运行通过 |
| 19 | 12_run_context_serialization | `12_run_context_serialization.py` | 1.01s | ✅ | 运行通过 |
| 20 | 13_human_in_the_loop | `13_human_in_the_loop.py` | 2.04s | ✅ | 运行通过 |
| 21 | 14_event_standardization | `14_event_standardization.py` | 2.25s | ✅ | 运行通过 |
| 22 | 15_multi_tenant_isolation | `15_multi_tenant_isolation.py` | 2.66s | ✅ | 运行通过 |
| 23 | 16_lifecycle_hooks | `16_lifecycle_hooks.py` | 2.42s | ✅ | 运行通过 |
| 24 | 17_checkpoint_handoff_resume | `17_checkpoint_handoff_resume.py` | 1.02s | ✅ | 运行通过 |
| 25 | 18_model_cosplay | `18_model_cosplay.py` | 1.03s | ✅ | 运行通过 |
| 26 | 19_hitl_deterministic | `19_hitl_deterministic.py` | 1.01s | ✅ | 运行通过 |
| | **合计** | | **56.68s** | **26/26** | |

## 耗时分析

- **最快示例**：05_human_in_the_loop / 12_run_context_serialization / 19_hitl_deterministic (均为 1.01s)
- **最慢示例**：07_sync_async_stream (3.54s)
- **性能观察**：本次批跑合计 56.68s，整体耗时分布较均衡，主要集中在 07_sync_async_stream / 08_memory / 11_orchestration_enhancement 等示例。

## 已知问题

| 问题 | 严重程度 | 说明 |
|------|:--------:|------|
| 运行异常 | - | 无，26 个示例全部通过 |

## 运行方式

```bash
# 在 agentkit 目录执行
python examples/test_standard.py
```
