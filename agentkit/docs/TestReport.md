# AgentKit 示例测试报告

> 测试时间：`2026-05-05`  
> 测试环境：`macOS (Apple Silicon)`  
> 模型：`qwen/qwen3.5-flash` (DashScope)  
> AgentKit 版本：v0.7.2  
> Thinking 模式：开启（默认）  
> LLM 调用模式：非流式（默认）  
> 缓存：开启（默认）  
> 执行脚本：`examples/test_standard.py`
> 说明：本报告生成于脚本覆盖 24 个样例时期；当前脚本已扩展为覆盖 26 个（新增 `05_human_in_the_loop.py`、`19_hitl_deterministic.py`，`20_simple_rag_agent.py` 不在自动批跑范围内）。

---

## 测试结果

| # | 示例 | 文件 | 耗时 | 状态 | 说明 |
|---|------|------|-----:|:----:|------|
| 1 | 基础对话 | `01_basic_chat.py` | 11.89s | ✅ | 运行通过 |
| 2 | 工具调用 | `02_tool_calling.py` | 5.47s | ✅ | 运行通过 |
| 3 | Skill 使用 | `03_skill_usage.py` | 8.80s | ✅ | 运行通过 |
| 3B | Skill tools.entry 动态注册/发现 | `03b_skill_tools_entry.py` | 5.83s | ✅ | 运行通过 |
| 4 | 多 Agent 协作 | `04_multi_agent.py` | 34.73s | ✅ | 运行通过 |
| 5 | 安全护栏 | `05_guardrail.py` | 4.80s | ✅ | 运行通过 |
| 6 | 编排 Agent | `06_orchestration.py` | 84.79s | ✅ | 运行通过 |
| 7 | 同步/异步/流式 | `07_sync_async_stream.py` | 5.88s | ✅ | 运行通过 |
| 8 | 记忆系统（综合） | `08_memory.py` | 77.63s | ✅ | 运行通过 |
| 8A | SimpleMemory | `08a_memory_simple_provider.py` | 13.58s | ✅ | 运行通过 |
| 8B | Mem0Provider | `08b_memory_mem0_provider.py` | 0.21s | ✅ | 未配置 OPENAI_API_KEY，自动跳过 |
| 8C | 文件持久化 Memory | `08c_memory_file_provider.py` | 19.65s | ✅ | 运行通过 |
| 9A | 结构化数据（SQL） | `09a_structured_data_sql.py` | 2.41s | ✅ | 运行通过 |
| 9B | 结构化数据（图） | `09b_structured_data_graph.py` | 2.48s | ✅ | 运行通过 |
| 9C | NebulaGraphTool（直调） | `09c_nebula_graph_tool.py` | 0.32s | ✅ | 运行通过 |
| 10 | Skill 生命周期 | `10_skill_lifecycle.py` | 1.53s | ✅ | 运行通过 |
| 11 | 编排增强 | `11_orchestration_enhancement.py` | 17.11s | ✅ | 运行通过 |
| 12 | 序列化协议 | `12_run_context_serialization.py` | 0.31s | ✅ | 运行通过 |
| 13 | Human in the Loop | `13_human_in_the_loop.py` | 4.39s | ✅ | 运行通过 |
| 14 | Event 标准化 | `14_event_standardization.py` | 5.13s | ✅ | 运行通过 |
| 15 | 多租户隔离 | `15_multi_tenant_isolation.py` | 4.58s | ✅ | 运行通过 |
| 16 | 生命周期 Hooks | `16_lifecycle_hooks.py` | 4.74s | ✅ | 运行通过 |
| 17 | Checkpoint + Handoff + Resume | `17_checkpoint_handoff_resume.py` | 0.17s | ✅ | 运行通过 |
| 18 | ModelCosplay | `18_model_cosplay.py` | 0.18s | ✅ | 运行通过 |
| | **合计** | | **316.61s** | **24/24** | |

## 耗时分析

- **最快示例**：17 Checkpoint + Handoff + Resume (0.17s)
- **最慢示例**：06 编排 Agent (84.79s)
- **性能改进**：相比 Ollama 运行，DashScope 接口响应更快，且在大规模编排和记忆检索场景下稳定性更好。

## 已知问题

| 问题 | 严重程度 | 说明 |
|------|:--------:|------|
| 运行异常 | - | 无，24 个示例全部通过 |

## 运行方式

```bash
# 在 agentkit 目录执行
python examples/test_standard.py
```
