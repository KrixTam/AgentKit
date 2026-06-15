# AgentHub 参考手册

---

## 数据模型

### AgentManifest

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | `str` | Agent 名称 |
| `version` | `str` | Agent 版本（语义化版本 `major.minor.patch`） |
| `description` | `str` | Agent 描述 |
| `entry` | `str` | Agent 入口，支持 `module:attr` 或 `path.py:attr` |
| `skills` | `list[str]` | 关联的 Skill 标识列表 |
| `input_schema` | `dict` | 输入契约 |
| `output_schema` | `dict` | 输出契约 |
| `requires_human_input` | `bool` | 是否需要人工介入 |
| `schema` | `dict` | 历史兼容字段；当前实现会与 `input_schema` 双向归一化 |
| `runner_config` | `dict` | Runner 相关默认参数 |
| `model_cosplay` | `str \| dict \| null` | 通过 `agent.yaml` 为该 Agent 配置默认 ModelCosplay；调用请求中的 `model_cosplay` 优先级更高 |
| `tags` | `list[str]` | 标签 |

### `agent.rag.yaml.example` 字段对照

`agent.rag.yaml.example` 是针对 `SimpleRAGAgent + AgentHub` 的最小注册模板，位于 [agent.rag.yaml.example](file:///Users/krix/Trae/AgentKit/agenthub/docs/agent.rag.yaml.example)。

示例内容对应的关键字段说明如下：

| 字段 | 当前示例值 | 说明 |
|---|---|---|
| `name` | `demo-simple-rag` | 在 Hub 中注册后的 Agent 名称 |
| `version` | `1.0.0` | 语义化版本号 |
| `description` | `SimpleRAGAgent 最小可运行示例（AgentKit + AgentHub）` | 用于列表展示与排障说明 |
| `entry` | `./agentkit/examples/standard/20_simple_rag_agent.py:create_agent` | 使用 `path.py:attr` 入口，直接复用 AgentKit 示例中的无参工厂函数 |
| `skills` | `[]` | 当前示例未额外挂 Skill |
| `input_schema` | `{"input": "string"}` | 最小输入契约，仅要求 `input` 字符串 |
| `output_schema` | `{"final_output": "string"}` | 最小输出契约，匹配 `RunResult.final_output` |
| `requires_human_input` | `false` | RAG 示例默认不走 HITL 挂起 |
| `runner_config.max_turns` | `10` | 单次调用最大轮次 |
| `runner_config.default_hub_port` | `8008` | 示例默认 Hub 端口 |
| `tags` | `["demo", "rag"]` | 便于检索、分组与标识用途 |

补充约束：

- `entry` 指向的 `create_agent` 必须是**无参工厂函数**，并返回一个可运行的 AgentKit Agent 实例。
- `entry` 使用相对路径时，路径解析基于执行 `agenthub register` 时的当前工作目录。
- 该示例依赖 `SimpleRAGAgent` 默认读取 `./knowledge_base` 目录，因此注册前需先准备知识库文件。
- `SimpleRAGAgent` 默认会把知识库索引与内置记忆统一写入 `./.agentkit/rag/index.db`；如需自定义路径，请在入口脚本中调整 `storage_path`。
- 当前知识库输入支持 `txt/md/markdown/pdf`；如果使用 PDF，目标环境需额外安装 `ni.agentkit[pdf]` 或 `pypdf`。
- 如果目标环境没有配置可用模型（例如标准版示例所需 API Key），注册虽可成功，但运行时会在 Agent 实例加载或推理阶段失败。

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

### ResumeRequest

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_input` | `str` | 人工输入内容 |
| `suspension_id` | `str \| null` | 可选；指定恢复的挂起点（多挂起场景建议显式传入） |
| `idempotency_key` | `str \| null` | 可选；幂等键，重复提交会被忽略 |
| `trace_id` | `str \| null` | 可选；链路追踪标识 |

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
- `POST /api/v1/agents/{name}:{version}/stream`（SSE，内部按 `run_with_checkpoint` 执行并写入会话事件）
- `WS /api/v1/agents/{name}:{version}/ws`（`action=run|resume`）

### 会话管理

- `GET /api/v1/sessions?status=...`
- `GET /api/v1/sessions/{session_id}`
- `GET /api/v1/sessions/{session_id}/events`
- `POST /api/v1/sessions/{session_id}/resume`
- `DELETE /api/v1/sessions/{session_id}`

### HITL 工作台

- `GET /api/v1/hitl/suspended`
- `GET /api/v1/hitl/{session_id}/form?suspension_id=...`
- `POST /api/v1/hitl/{session_id}/submit`

### 运维接口

- `GET /healthz`
- `GET /metrics`
- `GET /playground`：内置联调控制台（可配置 Bearer Token，支持 invoke/stream、会话查询、HITL 提交、Registry 快捷注册）

---

## WebSocket 协议

### run

```json
{
  "action": "run",
  "authorization": "Bearer <token>",
  "input": "你好",
  "model_cosplay": "gpt-4o-mini",
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
  "suspension_id": "susp-001",
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
| `manifest` | 生成/处理 Agent Manifest（如 `manifest generate`） |
| `register` | 注册 Manifest |
| `unregister` | 下线指定版本（`name:version`） |
| `list` | 列出 Agent |
| `info` | 查看 Agent |
| `run` | 同步调用 |
| `chat` | 启动基于 Streamlit 的 Agent Chat 页面 |
| `trace` | 回放会话事件 |
| `session` | `list/get/resume/terminate` 会话管理 |

`manifest generate` 常用参数：

- `--entry`：Agent 入口（`module:attr` 或 `path.py:attr`，必填）
- `--output`：输出路径（默认 `./agent.yaml`）
- `--name` / `--version` / `--description`：覆盖自动推断字段
- `--max-turns`：设置 `runner_config.max_turns`
- `--force`：覆盖已有文件

`run` 子命令常用参数：

- `--input`：请求输入（必填）
- `--model-cosplay`：运行时改写模型（仅对开启 ModelCosplay 的 Agent 生效）
- `--user-id` / `--session-id`：用户与会话透传

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
| `AGENTHUB_LOG_FILE` | `.agenthub/agenthub.log` | AgentHub 日志文件路径 |
| `AGENTHUB_LOG_LEVEL` | `INFO` | AgentHub 日志级别 |

---

## 可观测与审计字段

- `/metrics` 输出聚合指标：`agenthub_requests_total`、`agenthub_errors_total`、`agenthub_suspended_total`、`agenthub_completed_total`、`agenthub_active_sessions`、`agenthub_latency_p95_ms`
- 结构化审计日志会追加请求级性能字段：`db_ops`（数据库操作次数）、`event_write_ms`（事件写入耗时）、`agent_resolve_ms`（Agent 解析耗时）

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
- `append_events(session_id, events)`（批量写入，返回 `seq` 列表）
- `list_events(session_id)`（按 `seq` 升序）
- `get_latest_event(session_id, event_type=None, suspension_id=None)`（按条件获取最新事件）
- `save_checkpoint/load_checkpoint/delete_checkpoint`
- `terminate(session_id)`
