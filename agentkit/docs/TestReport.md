# AgentKit 示例测试报告

> 测试时间：`2026-06-15`  
> 测试环境：`macOS (Apple Silicon)`  
> 模型：`qwen/qwen3.6-flash` (DashScope)  
> AgentKit 版本：v0.7.3  
> Thinking 模式：开启（默认）  
> LLM 调用模式：非流式（默认）  
> 缓存：开启（默认）  
> 执行脚本：`examples/test_standard.py`
> 说明：本报告由 `examples/test_standard.py` 批跑生成，共覆盖 26 个样例；`20_simple_rag_agent.py` 不在自动批跑范围内。

---

## 测试结果

| # | 示例 | 文件 | 耗时 | 状态 | 说明 |
|---|------|------|-----:|:----:|------|
| 1 | 01_basic_chat | `01_basic_chat.py` | 6.67s | ✅ | 运行通过 |
| 2 | 02_tool_calling | `02_tool_calling.py` | 10.60s | ✅ | 运行通过 |
| 3 | 03_skill_usage | `03_skill_usage.py` | 11.34s | ✅ | 运行通过 |
| 4 | 03b_skill_tools_entry | `03b_skill_tools_entry.py` | 7.69s | ✅ | 运行通过 |
| 5 | 04_multi_agent | `04_multi_agent.py` | 54.06s | ✅ | 运行通过 |
| 6 | 05_guardrail | `05_guardrail.py` | 8.95s | ✅ | 运行通过 |
| 7 | 05_human_in_the_loop | `05_human_in_the_loop.py` | 0.25s | ✅ | 运行通过 |
| 8 | 06_orchestration | `06_orchestration.py` | 41.62s | ✅ | 运行通过 |
| 9 | 07_sync_async_stream | `07_sync_async_stream.py` | 16.21s | ✅ | 运行通过 |
| 10 | 08_memory | `08_memory.py` | 31.10s | ✅ | 运行通过 |
| 11 | 08a_memory_simple_provider | `08a_memory_simple_provider.py` | 8.81s | ✅ | 运行通过 |
| 12 | 08b_memory_mem0_provider | `08b_memory_mem0_provider.py` | 0.25s | ✅ | 运行通过 |
| 13 | 08c_memory_file_provider | `08c_memory_file_provider.py` | 10.82s | ✅ | 运行通过 |
| 14 | 09a_structured_data_sql | `09a_structured_data_sql.py` | 6.37s | ✅ | 运行通过 |
| 15 | 09b_structured_data_graph | `09b_structured_data_graph.py` | 2.58s | ✅ | 运行通过 |
| 16 | 09c_nebula_graph_tool | `09c_nebula_graph_tool.py` | 0.34s | ✅ | 运行通过 |
| 17 | 10_skill_lifecycle | `10_skill_lifecycle.py` | 2.98s | ✅ | 运行通过 |
| 18 | 11_orchestration_enhancement | `11_orchestration_enhancement.py` | 3.41s | ✅ | 运行通过 |
| 19 | 12_run_context_serialization | `12_run_context_serialization.py` | 0.18s | ✅ | 运行通过 |
| 20 | 13_human_in_the_loop | `13_human_in_the_loop.py` | 6.36s | ✅ | 运行通过 |
| 21 | 14_event_standardization | `14_event_standardization.py` | 2.87s | ✅ | 运行通过 |
| 22 | 15_multi_tenant_isolation | `15_multi_tenant_isolation.py` | 8.43s | ✅ | 运行通过 |
| 23 | 16_lifecycle_hooks | `16_lifecycle_hooks.py` | 4.92s | ✅ | 运行通过 |
| 24 | 17_checkpoint_handoff_resume | `17_checkpoint_handoff_resume.py` | 0.19s | ✅ | 运行通过 |
| 25 | 18_model_cosplay | `18_model_cosplay.py` | 0.20s | ✅ | 运行通过 |
| 26 | 19_hitl_deterministic | `19_hitl_deterministic.py` | 0.19s | ✅ | 运行通过 |
| | **合计** | | **247.37s** | **26/26** | |

## 耗时分析

- **最快示例**：12_run_context_serialization (0.18s)
- **最慢示例**：04_multi_agent (54.06s)
- **性能改进**：本次批跑合计 247.37s，耗时主要集中在 04_multi_agent / 06_orchestration / 08_memory 等编排类示例。

## 已知问题

| 问题 | 严重程度 | 说明 |
|------|:--------:|------|
| 运行异常 | - | 无，26 个示例全部通过 |

## 运行方式

```bash
# 在 agentkit 目录执行
python examples/test_standard.py
```
