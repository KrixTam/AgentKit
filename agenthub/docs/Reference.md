# AgentHub 参考手册

---

## 数据模型

### AgentManifest

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | `str` | Agent 名称 |
| `version` | `str` | Agent 版本 |
| `entry` | `str` | `module:attr` 入口 |
| `schema` | `dict` | 输入/输出契约描述（Manifest 语义） |
| `runner_config` | `dict` | Runner 相关默认参数 |
| `tags` | `list[str]` | 标签 |

### SessionStatus

- `running`
- `suspended`
- `completed`
- `error`
- `expired`
- `terminated`

### ApiResponse

统一响应结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

---

## HTTP API

### 注册与发现

- `POST /v1/agents/register`
- `GET /v1/agents`
- `GET /v1/agents/{name}`
- `DELETE /v1/agents/{name}/{version}`
- `POST /v1/agents/{name}/aliases/{alias}?version=...`

### 调用网关

- `POST /v1/agents/{name}/invoke?version=...`
- `GET /v1/agents/{name}/stream?...`（SSE）
- `WS /v1/ws`（`action=run|resume`）

### 会话管理

- `GET /v1/sessions?status=...`
- `GET /v1/sessions/{session_id}`
- `GET /v1/sessions/{session_id}/events`
- `POST /v1/sessions/{session_id}/resume`
- `POST /v1/sessions/{session_id}/terminate`

### HITL 工作台

- `GET /v1/hitl/suspended`
- `GET /v1/hitl/{session_id}/form`
- `POST /v1/hitl/{session_id}/submit`

### 运维接口

- `GET /healthz`
- `GET /metrics`
- `GET /playground`

---

## WebSocket 协议

### run

```json
{
  "action": "run",
  "api_key": "...",
  "agent": "demo-agent",
  "version": "stable",
  "input": "你好",
  "user_id": "u1",
  "session_id": "s1",
  "trace_id": "t1"
}
```

### resume

```json
{
  "action": "resume",
  "api_key": "...",
  "session_id": "s1",
  "user_input": "yes",
  "idempotency_key": "resume-001"
}
```

---

## CLI

安装：

```bash
pip install ni.agenthub
```

入口命令：`agenthub`

| 子命令 | 用途 |
|---|---|
| `serve` | 启动服务 |
| `register` | 注册 Manifest |
| `list` | 列出 Agent |
| `info` | 查看 Agent |
| `run` | 同步调用 |
| `trace` | 回放会话事件 |
| `session` | 查询/恢复/终止会话 |

全局参数：

- `--server`：默认 `http://127.0.0.1:8008`
- `--json`：机器可读输出

退出码约定：

- `0`：成功
- `2`：请求失败（可用于脚本自动判断）

---

## 配置项（环境变量）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AGENTHUB_HOST` | `0.0.0.0` | 监听地址 |
| `AGENTHUB_PORT` | `8008` | 监听端口 |
| `AGENTHUB_STORE` | `sqlite` | 存储类型：`memory/sqlite` |
| `AGENTHUB_SQLITE_PATH` | `.agenthub/agenthub.db` | SQLite 路径 |
| `AGENTHUB_API_KEY` | 空 | API Key（为空则不鉴权） |
| `AGENTHUB_MAX_CONCURRENCY_PER_USER` | `8` | 单用户并发上限 |
| `AGENTHUB_RATE_LIMIT_PER_MINUTE` | `120` | 单用户每分钟请求上限 |

---

## 存储接口

### RegistryStore

- `register(manifest, aliases)`
- `unregister(name, version)`
- `list_versions(name)`
- `list_all()`
- `resolve(name, version_or_alias)`
- `set_alias(name, alias, version)`

### SessionStore

- `create(session)`
- `get(session_id)`
- `update_status(session_id, status, error=None)`
- `list_sessions(status=None)`
- `append_event(session_id, event)`（返回 `seq`）
- `list_events(session_id)`（按 `seq` 升序）
- `save_checkpoint/load_checkpoint/delete_checkpoint`
- `terminate(session_id)`
