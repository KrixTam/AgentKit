# AgentHub 测试报告

> 测试时间：`2026-04-21`  
> 测试环境：`macOS (Apple Silicon)`  
> AgentHub 版本：`v0.3.2`  
> AgentKit 版本：`v0.6.1`  
> 存储模式：`memory + sqlite`

---

## 测试结果

| # | 测试项 | 场景 | 状态 | 说明 |
|---|---|---|:---:|---|
| 1 | 注册中心 | `agent.yaml` 校验（字段缺失/格式错误） | ✅ | `test_manifest.py` 覆盖，字段级错误可定位 |
| 2 | 注册中心 | 注册 / 查询 / 下线 / 别名 latest/stable | ✅ | `test_acceptance_gateway.py` 覆盖注册、查询、别名 |
| 3 | REST 网关 | `invoke` 同步调用 | ✅ | 返回统一 `ApiResponse`，包含 `session_id/trace_id` |
| 4 | SSE 网关 | `stream` 事件透传 | ✅ | 事件流包含 `data:` 与 `final_output` |
| 5 | WS 网关 | `run` / `resume` 双向通道 | ✅ | 挂起后可恢复，事件链路完整 |
| 6 | 会话管理 | `list/get/events/replay` | ✅ | 事件按 `seq` 顺序回放，状态查询正常 |
| 7 | HITL 工作台 | suspended 列表 + form + submit | ✅ | 支持 schema/JSON 回退与幂等防重 |
| 8 | 存储契约 | InMemory 与 SQLite 行为一致性 | ✅ | `test_stores.py` 对齐验证通过 |
| 9 | SQLite 持久化 | 重启后 registry/session/checkpoint 恢复 | ✅ | SQLite 重建 App 后注册记录可恢复 |
| 10 | 鉴权 | Bearer 鉴权（静态 token）开启/关闭 | ✅ | 未授权返回 401，`Authorization: Bearer <token>` 授权访问正常 |
| 11 | 配额 | 并发上限与频率限制 | ⚠️ | 当前未覆盖超限断言，建议补充专项测试 |
| 12 | 可观测 | `/healthz` 与 `/metrics` | ✅ | 指标端点返回 Prometheus 文本 |
| 13 | 审计 | who/when/what/result | ⚠️ | 代码已结构化日志输出，当前未做断言校验 |

---

## 关键耗时（可选）

| 场景 | 耗时 | 备注 |
|---|---:|---|
| 全量测试套件（15 项） | 0.28s | `python -m pytest ./agenthub/tests -q`（`15 passed`） |
| 注册 Agent | 已覆盖 | 含 manifest 校验 |
| 首次 invoke | 已覆盖 | 含 entry 首次加载与原型缓存路径 |
| SSE 流式会话 | 已覆盖 | 含事件持久化 |
| WS run + resume | 已覆盖 | 含 checkpoint 与恢复 |

---

## 契约一致性检查（AgentKit ↔ AgentHub）

| 契约项 | 检查结论 | 备注 |
|---|---|---|
| Event 契约 | ✅ | SSE/WS/回放场景均验证事件字段与顺序 |
| Session 契约 | ✅ | `session_id` 在 invoke/stream/ws/hitl 全链路一致 |
| HumanInput 契约 | ✅ | suspend + submit/resume 一致性通过 |
| 存储契约 | ✅ | checkpoint 与事件落盘映射验证通过 |
| 兼容契约 | ⚠️ | 主要路径通过，建议补充“全部可选能力关闭”专项回归 |

---

## 已知问题

| 问题 | 严重程度 | 说明 |
|---|:---:|---|
| 验收覆盖缺口 | 中 | 配额超限与审计日志断言尚未纳入自动化测试 |

---

## 回归建议命令

```bash
# 1) 运行 AgentHub 验收测试集合（推荐）
python -m pytest ./agenthub/tests/test_acceptance_gateway.py -q

# 2) 运行 AgentHub 全量测试（验收 + 存储契约 + manifest 校验）
python -m pytest ./agenthub/tests -q

# 3) 启动服务（SQLite）
agenthub serve --store sqlite --sqlite-path .agenthub/agenthub.db

# 4) 运行一轮最小冒烟（示例）
agenthub register ./agent.yaml --alias stable --alias latest
agenthub run demo-agent --input "你好"
```
