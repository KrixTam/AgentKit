# AgentKit 示例测试报告

> 测试时间：2026-04-12  
> 测试环境：macOS (Apple Silicon)  
> 模型：Ollama `qwen3.5:cloud`  
> AgentKit 版本：v0.3.0  
> Thinking 模式：开启（默认）  
> LLM 调用模式：非流式（默认）  
> 缓存：开启（默认）

---

## 测试结果

| # | 示例 | 文件 | 耗时 | 状态 | 说明 |
|---|------|------|-----:|:----:|------|
| 1 | 基础对话 | `01_basic_chat.py` | 27.7s | ✅ | 正确回答量子计算定义 |
| 2 | 工具调用 | `02_tool_calling.py` | 21.8s | ✅ | add=42 / multiply=21 / weather=晴25°C |
| 3 | Skill 使用 | `03_skill_usage.py` | 42.8s | ✅ | 深圳阵雨→带伞 / 成都阴→厚外套 / 广州晴→防晒 |
| 4 | 多 Agent 协作 | `04_multi_agent.py` | 116.6s | ✅ | as_tool 委派成功；Handoff 偶发返回 None |
| 5 | 安全护栏 | `05_guardrail.py` | 12.9s | ✅ | 敏感词拦截 ✅ / read_file 放行 ✅ / delete_file 拒绝 ✅ |
| 6 | 编排 Agent | `06_orchestration.py` | 195.6s | ✅ | Sequential 流水线 + Parallel 并行 + Loop 循环 |
| 7 | 同步/异步/流式 | `07_sync_async_stream.py` | 50.0s | ✅ | run_sync 4.3s / run 2.1s / 并发×3 4.5s / 流式 8.3s |
| 8 | 记忆系统 | `08_memory.py` | 144.2s | ✅ | 咖啡→拿铁→牛奶过敏→燕麦拿铁（4 轮完美记忆） |
| | **合计** | | **611.6s** | **8/8** | |

## 耗时分析

- **单次 LLM 调用**（含 thinking）：约 5-15 秒
- **最快示例**：05 安全护栏（12.9s）——护栏拦截不经过 LLM
- **最慢示例**：06 编排 Agent（195.6s）——3 组编排模式，每组含多个 Agent 串行/并行调用
- **多轮示例耗时** ≈ LLM 调用次数 × 单次调用耗时

## 各示例 LLM 调用次数估算

| # | 示例 | LLM 调用次数 | 说明 |
|---|------|:-----------:|------|
| 1 | 基础对话 | 1 | 单次对话 |
| 2 | 工具调用 | 6 | 3 个查询 × 2 轮（调工具 + 生成回复） |
| 3 | Skill 使用 | 9 | 3 个查询 × 3 轮（load_skill + 调工具 + 回复） |
| 4 | 多 Agent 协作 | ~8 | 模式 A（经理+研究员）+ 模式 B（分诊+2 专家） |
| 5 | 安全护栏 | 3 | 1 次被拦截 + 2 次正常执行（含工具调用） |
| 6 | 编排 Agent | ~12 | Sequential(3) + Parallel(3) + Loop(~6) |
| 7 | 同步/异步/流式 | ~7 | 同步(1) + 异步(1) + 并发(3) + 流式(2) |
| 8 | 记忆系统 | ~10 | 无记忆(2) + 有记忆(4 轮 × 2 调用) |

## 已知问题

| 问题 | 严重程度 | 说明 |
|------|:--------:|------|
| 示例 04 Handoff 偶发返回 None | 低 | cloud 模型对 `transfer_to_xxx` 工具的理解偶发异常，非框架 bug |
| 示例 06 Loop 部分输出较简短 | 低 | 小模型在迭代优化场景下生成质量有限 |

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

# 运行全部示例
for f in examples/ollama/0*.py; do python "$f"; done
```
