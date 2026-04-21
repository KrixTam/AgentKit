# AgentHub

> AgentKit 的 Control Plane（管控平面）：提供注册发现、统一调用网关、会话管理与可观测能力。

---

## 文档目录

- [QuickStart.md](QuickStart.md) — 快速上手（启动服务、注册 Agent、调用与回放）
- [Architecture.md](Architecture.md) — 架构设计与 AgentKit 契约映射
- [Reference.md](Reference.md) — API / CLI / 配置 / 存储接口参考
- [agent.yaml.example](agent.yaml.example) — 可直接复制为 `agent.yaml` 的清单模板

---

## 安装

```bash
pip install ni.agenthub
```

---

## 当前实现范围（v0.3.3）

- 注册发现：`agent.yaml` 清单校验、注册、查询、下线、别名（`latest`/`stable`）
- 统一网关：REST 同步调用、SSE 事件流、WS 双向通道（run/resume）
- 模型改写：支持请求级 `model_cosplay`，并支持通过 `agent.yaml` 的 `model_cosplay` 配置默认改写（请求参数优先）
- 会话管理：状态机、事件回放、resume、terminate、HITL 待办与表单
- 持久化后端：`memory` / `sqlite` 二选一（行为一致）
- 平台治理：Bearer 鉴权（静态 token 或 OAuth/OIDC introspection，可选开启）、并发与速率配额、结构化审计日志
- 可观测：`/healthz`、`/metrics`（Prometheus 文本格式，延迟统计为滑动窗口）、基础 Playground
- 性能审计：请求级结构化审计日志包含 `db_ops`、`event_write_ms`、`agent_resolve_ms`
- 存储优化：同步 `invoke` 路径支持批量事件写入（`append_events`）；HITL 表单支持按 `suspension_id` 定向读取最新挂起事件（`get_latest_event`）

---

## 验收测试集合

- 入口：`agenthub/tests/test_acceptance_gateway.py`
- 覆盖：注册发现、REST/SSE/WS、HITL 恢复、会话回放、SQLite 持久化、鉴权与指标
- 命令：`python -m pytest ./agenthub/tests/test_acceptance_gateway.py -q`

---

## 兼容与边界

- AgentHub 不替换 AgentKit 执行引擎，仅编排调用 `Runner.run` / `run_streamed` / `run_with_checkpoint` / `resume`
- 所有能力默认可选：不开启鉴权/配额时，保持最小接入成本
- `memory` 存储模式会在重启后丢失数据；`sqlite` 提供单机持久化
