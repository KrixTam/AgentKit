# AgentHub 参考手册

---

## 数据模型

### AgentManifest

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | `str` | Agent 名称 |
| `version` | `str` | Agent 版本（语义化版本 `major.minor.patch`） |
| `description` | `str` | Agent 描述 |
| `entry` | `str` | `module:attr` 入口 |
| `skills` | `list[str]` | 关联的 Skill 标识列表 |
| `input_schema` | `dict` | 输入契约 |
| `output_schema` | `dict` | 输出契约 |
| `requires_human_input` | `bool` | 是否需要人工介入 |
| `schema` | `dict` | 历史兼容字段；当前实现会与 `input_schema` 双向归一化 |
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

### InvokeRequest

| 字段 | 类型 | 说明 |
|---|---|---|
| `input` | `str` | 用户输入 |
| `model_cosplay` | `str \| dict \| null` | 运行时模型伪装配置；仅对开启 `ModelCosplay` 的 Agent 生效 |
| `user_id` | `str \| null` | 用户标识 |
| `session_id` | `str \| null` | 会话标识 |
| `trace_id` | `str \| null` | 链路追踪标识 |
| `context` | `dict \| null` | 可选上下文 |
| `max_turns` | `int` | 本次调用最大轮次 |

---

## HTTP API

### 注册与发现

- `POST /api/v1/registry/agents`
- `GET /api/v1/registry/agents`
- `GET /api/v1/registry/agents/{name}`
- `DELETE /api/v1/registry/agents/{name}:{version}`
- `POST /api/v1/registry/agents/{name}/aliases/{alias}?version=...`

### 调用网关

- `POST /api/v1/agents/{name}:{version}/invoke`
- `POST /api/v1/agents/{name}:{version}/stream`（SSE）
- `WS /api/v1/agents/{name}:{version}/ws`（`action=run|resume`）

### 会话管理

- `GET /api/v1/sessions?status=...`
- `GET /api/v1/sessions/{session_id}`
- `GET /api/v1/sessions/{session_id}/events`
- `POST /api/v1/sessions/{session_id}/resume`
- `DELETE /api/v1/sessions/{session_id}`

### HITL 工作台

- `GET /api/v1/hitl/suspended`
- `GET /api/v1/hitl/{session_id}/form`
- `POST /api/v1/hitl/{session_id}/submit`

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
  "authorization": "Bearer <token>",
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
  "authorization": "Bearer <token>",
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
| `unregister` | 下线指定版本（`name:version`） |
| `list` | 列出 Agent |
| `info` | 查看 Agent |
| `run` | 同步调用 |
| `trace` | 回放会话事件 |
| `session` | `list/get/resume/terminate` 会话管理 |

全局参数：

- `--server`：默认 `http://127.0.0.1:8008`
- `--token`：Bearer token（默认读取 `AGENTHUB_TOKEN`）
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
| `AGENTHUB_API_KEY` | 空 | 静态 Bearer token（为空则可关闭鉴权） |
| `AGENTHUB_OAUTH_INTROSPECTION_URL` | 空 | OAuth2/OIDC Introspection 地址 |
| `AGENTHUB_OAUTH_CLIENT_ID` | 空 | Introspection Client ID |
| `AGENTHUB_OAUTH_CLIENT_SECRET` | 空 | Introspection Client Secret |
| `AGENTHUB_OIDC_ISSUER` | 空 | 可选 issuer 校验 |
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
