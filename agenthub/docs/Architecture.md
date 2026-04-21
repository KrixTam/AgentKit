# AgentHub 架构设计

---

## 定位

AgentHub 是 AgentKit 的 Control Plane：

- AgentKit 负责执行内核（Agent/Runner/Event/Context）
- AgentHub 负责平台能力（注册发现、网关、会话、治理、观测）

AgentHub 不替换 AgentKit 运行时主循环，仅以适配方式调用：

- `Runner.run`
- `Runner.run_streamed`
- `Runner.run_with_checkpoint`
- `Runner.resume`

---

## 分层结构

```
┌────────────────────────────────────────────┐
│ Gateway Layer (FastAPI)                   │
│ REST / SSE / WS / HITL / Health / Metrics │
├────────────────────────────────────────────┤
│ Runtime Layer                              │
│ 会话状态机 / 配额 / 审计 / 指标 / 适配器      │
├────────────────────────────────────────────┤
│ Store Layer                                │
│ RegistryStore / SessionStore               │
│  ├─ InMemory                               │
│  └─ SQLite                                 │
├────────────────────────────────────────────┤
│ AgentKit Runtime                            │
│ Runner + ContextStore + Event              │
└────────────────────────────────────────────┘
```

---

## 核心流程

### 1) REST 同步调用

1. 网关解析请求与鉴权（可选）。
2. 通过 Registry 解析 `{name, version|alias}` 到 Manifest。
3. 命中 Agent 原型缓存（未命中时加载 `entry=module:attr`），并深拷贝得到请求级实例。
4. 应用模型改写策略：优先请求参数 `model_cosplay`，否则使用 Manifest 的 `model_cosplay` 默认值（仅对开启能力的 Agent 生效）。
5. 创建/复用会话记录（`session_id`、`trace_id`、`user_id`）。
6. 调用 `Runner.run(...)` 获取 `RunResult`。
7. 事件顺序写入 SessionStore（带 `seq`）；同步 `invoke` 路径使用批量写入（`append_events`）降低存储往返。
8. 返回统一响应结构 `ApiResponse`。

### 2) SSE 流式调用

1. 调用 `Runner.run_streamed(...)`。
2. 每个 Event 落盘后按 SSE 透传。
3. 断连时若状态仍为 `running`，标记为 `expired`。

### 3) WS 双向调用（HITL）

1. `action=run`：调用 `run_with_checkpoint(...)`，可挂起。
2. `action=resume`：调用 `resume(...)`，支持 `suspension_id` 精准恢复与幂等键防重。
3. WS 断连时清理会话状态一致性。

---

## 会话状态机

```
running -> suspended -> running -> completed
running -> error
running -> expired
running/suspended -> terminated
```

状态定义见 `SessionStatus`：

- `running`
- `suspended`
- `completed`
- `error`
- `expired`
- `terminated`

---

## 存储策略

统一契约：

- `RegistryStore`
- `SessionStore`

当前 `SessionStore` 契约除单条 `append_event` 外，还支持：

- `append_events`：批量事件写入（同步 `invoke` 走单次批量落盘）
- `get_latest_event`：按条件获取最新事件（HITL 表单按 `suspension_id` 精准查询）

两种实现：

- `InMemory*Store`：本地调试，重启丢失
- `SQLite*Store`：单机持久化，自动建表与索引

SQLite 关键表：

- `registry` / `aliases`
- `sessions`
- `events`（按 `session_id + seq` 顺序）
- `session_event_seq`（每会话事件序号计数，避免 `MAX(seq)` 热点）
- `checkpoints`
- `schema_migrations`

---

## 治理与观测

- 鉴权：`Authorization: Bearer <token>`（静态 token 或 OAuth/OIDC introspection，可选）
- 配额：`tenant:user` 维度并发与每分钟速率
- 审计：结构化日志（JSON）
- 指标：`requests/errors/suspended/completed/active/latency_p95`（延迟统计使用滑动窗口）
- 性能观测：请求级 `db_ops`、`event_write_ms`、`agent_resolve_ms`
- 运维：`/healthz` + `/metrics`

---

## 契约映射（AgentKit ↔ AgentHub）

- Event 契约：Hub 不改 Event 字段，按原样透传并持久化
- Session 契约：`session_id` 在 REST/SSE/WS 全通道透传
- HumanInput 契约：挂起事件中的 `form_schema` 优先渲染，失败回退 JSON 输入
- 存储契约：checkpoint 由 Hub `ContextStore` 适配写入 `SessionStore`
- 兼容契约：关闭鉴权/配额等新增能力时，退化为最小转发行为
