# AgentKit 示例测试报告

> 测试时间：2026-04-18  
> 测试环境：macOS (Apple Silicon)  
> 模型：Ollama `qwen3.5:cloud`  
> AgentKit 版本：v0.4.0  
> Thinking 模式：开启（默认）  
> LLM 调用模式：非流式（默认）  
> 缓存：开启（默认）

---

## 测试结果

| # | 示例 | 文件 | 耗时 | 状态 | 说明 |
|---|------|------|-----:|:----:|------|
| 1 | 基础对话 | `01_basic_chat.py` | 24.28s | ✅ | 正确回答量子计算定义 |
| 2 | 工具调用 | `02_tool_calling.py` | 38.29s | ✅ | add=42 / multiply=21 / weather=晴25°C |
| 3 | Skill 使用 | `03_skill_usage.py` | 22.36s | ✅ | 三次查询均正确，Skill 加载与工具调用正常 |
| 4 | 多 Agent 协作 | `04_multi_agent.py` | 177.43s | ✅ | as_tool 与 Handoff 两条路径均通过 |
| 5 | 安全护栏 | `05_guardrail.py` | 7.36s | ✅ | 敏感词拦截 ✅ / read_file 放行 ✅ / delete_file 拒绝 ✅ |
| 6 | 编排 Agent | `06_orchestration.py` | 144.72s | ✅ | Sequential + Parallel + Loop 三段流程均通过 |
| 7 | 同步/异步/流式 | `07_sync_async_stream.py` | 11.04s | ✅ | run_sync / run / 并发 / 流式四种路径均通过 |
| 8 | 记忆系统 | `08_memory.py` | 156.65s | ✅ | 流程完整通过，本轮无记忆阶段输出正常 |
| 9A | 结构化数据（SQL） | `09a_structured_data_sql.py` | 3.41s | ✅ | SQLite Mock 查询成功 |
| 9B | 结构化数据（图） | `09b_structured_data_graph.py` | 5.28s | ✅ | Nebula Mock 返回成功 |
| 10 | Skill 生命周期 | `10_skill_lifecycle.py` | 1.63s | ✅ | on_load / on_unload 路径可执行，示例运行通过 |
| 11 | 编排增强 | `11_orchestration_enhancement.py` | 104.73s | ✅ | loop_condition 生效；early_exit 触发并取消慢分支 |
| 12 | 序列化协议 | `12_run_context_serialization.py` | 0.30s | ✅ | 自定义对象 `__ak_serialize__` 和状态恢复可正常运行 |
| 13 | Human in the Loop | `13_human_in_the_loop.py` | 8.84s | ✅ | 工具触发挂起、存储 Checkpoint、人工介入后 `resume` 恢复执行均成功 |
| 14 | Event 标准化 | `14_event_standardization.py` | 7.17s | ✅ | 所有事件类型严格遵循 `EventType`，强类型校验拦截功能正常 |
| 15 | 多租户隔离 | `15_multi_tenant_isolation.py` | 0.29s | ✅ | Memory 与 Context 按 user_id 严格隔离，监控日志正常输出 |
| 16 | 生命周期 Hooks | `16_lifecycle_hooks.py` | 0.26s | ✅ | before/after 各级回调正常执行，改写响应生效，Hook 异常降级不崩溃 |
| | **合计** | | **714.04s** | **17/17** | |

## 耗时分析

- **单次 LLM 调用**（含 thinking）：约 2-20 秒（受任务复杂度和工具轮次影响）
- **最快示例**：16 生命周期 Hooks（0.26s）——本轮模型不可用分支快速返回
- **最慢示例**：4 多 Agent 协作（177.43s）——跨 Agent 协作包含多轮工具与交接链路
- **多轮示例耗时** ≈ LLM 调用次数 × 单次调用耗时

## 各示例 LLM 调用次数估算

| # | 示例 | LLM 调用次数 | 说明 |
|---|------|:-----------:|------|
| 1 | 基础对话 | 1 | 单次对话 |
| 2 | 工具调用 | ~6 | 3 个查询 × 2 轮（调工具 + 生成回复） |
| 3 | Skill 使用 | ~9 | 3 个查询 × 3 轮（load_skill + 调工具 + 回复） |
| 4 | 多 Agent 协作 | ~8 | 模式 A（经理+研究员）+ 模式 B（分诊+2 专家） |
| 5 | 安全护栏 | ~3 | 1 次被拦截 + 2 次正常执行（含工具调用） |
| 6 | 编排 Agent | ~12 | Sequential(3) + Parallel(3) + Loop(~6) |
| 7 | 同步/异步/流式 | ~7 | 同步(1) + 异步(1) + 并发(3) + 流式(2) |
| 8 | 记忆系统 | ~10 | 无记忆(2) + 有记忆(4 轮 × 2 调用) |
| 9A | 结构化数据（SQL） | ~2 | 参数化查询 + 汇总回复 |
| 9B | 结构化数据（图） | ~2 | NebulaGraphTool 调用 + 汇总回复 |
| 10 | Skill 生命周期 | 1 | 单轮对话，验证生命周期流程 |
| 11 | 编排增强 | ~4 | Loop + Parallel early_exit 事件路径 |
| 12 | RunContext 序列化 | 0 | 纯本地上下文序列化与反序列化 |
| 13 | HITL 断点续跑 | ~3 | 挂起前 1-2 轮 + 恢复后 1 轮 |
| 14 | 事件协议标准化 | 1 | 单轮响应 + 标准事件输出 |
| 15 | 多租户隔离 | ~3 | 多 Session 验证 user_id 隔离与资源释放日志 |
| 16 | 生命周期 Hooks | ~2 | Hook 拦截 + 异常降级路径验证 |

## 已知问题

| 问题 | 严重程度 | 说明 |
|------|:--------:|------|
| 本轮未发现阻塞性问题 | - | 17 个示例均通过；未复现 Handoff 返回 `None` 与无记忆阶段空输出 |

## 配置说明

本次测试使用以下默认配置：

```python
Agent(
    model="ollama/qwen3.5:cloud",
    enable_cache=True,           # LLM 响应缓存（默认开启）
    cache_ttl=300,               # 缓存有效期 300 秒
    memory_async_write=True,     # 记忆异步写入（示例 08 为 False）
)
```

OllamaAdapter 配置：
- **Thinking 模式**：开启（默认 `think=True`）
- **调用模式**：非流式（`stream=False`）
- **超时**：300 秒

## 运行方式

```bash
# 运行单个示例
python examples/ollama/01_basic_chat.py

# 运行全部示例（含 09a/09b 与 10-16）
for f in examples/ollama/*.py; do
  [[ "$(basename "$f")" == "__init__.py" ]] && continue
  python "$f"
done
```
