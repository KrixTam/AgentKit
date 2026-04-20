# AgentHub 快速入门

> 本文档基于当前代码实现（发行包：`ni.agenthub==0.3.0`，运行命令：`agenthub`）。

---

## 1. 安装与启动

```bash
pip install ni.agenthub
```

开发模式（可选）：

```bash
cd agenthub
pip install -e .
```

### SQLite 模式（推荐）

```bash
agenthub serve --store sqlite --sqlite-path .agenthub/agenthub.db
```

### 内存模式（轻量调试）

```bash
agenthub serve --store memory
```

> 内存模式重启后会丢失注册与会话数据。

---

## 2. 准备 `agent.yaml`

推荐直接使用项目内置模板：

```bash
cp ./docs/agent.yaml.example ./agent.yaml
```

```yaml
name: demo-echo
version: "1.0.0"
description: "示例 Echo Agent"
entry: agenthub.demo_agent:create_agent
skills: []
input_schema:
  type: object
  properties:
    input:
      type: string
  required:
    - input
output_schema:
  type: object
  properties:
    final_output:
      type: string
requires_human_input: false
runner_config:
  max_turns: 10
  default_hub_port: 8008
tags: [demo, stable]
```

`entry` 必须是 `module:attr` 格式；若校验失败，服务端会返回字段级错误信息。
上述示例可直接用（将 `agent.yaml.example` 重命名/复制为 `agent.yaml` 后可注册并调用）。

---

## 3. 注册与发现

```bash
# 注册并打上别名
agenthub register ./agent.yaml --alias stable --alias latest

# 列出所有 Agent 版本
agenthub list

# 查看指定 Agent
agenthub info demo-echo
```

---

## 4. 同步调用（REST）

```bash
agenthub run demo-echo --input "你好"
# 指定 ModelCosplay（仅对开启该能力的 Agent 生效）
agenthub run demo-echo --input "你好" --model-cosplay "gpt-4o-mini"
```

REST 对应接口：

```http
POST /api/v1/agents/{name}:{version_or_alias}/invoke
Authorization: Bearer <token>
Content-Type: application/json
{
  "input": "...",
  "model_cosplay": "gpt-4o-mini",
  "user_id": "u1",
  "session_id": "s1",
  "trace_id": "t1",
  "context": {},
  "max_turns": 10
}
```

---

## 5. 流式调用（SSE）

```bash
curl -N \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:8008/api/v1/agents/demo-echo:stable/stream" \
  -d '{"input":"你好","user_id":"u1","session_id":"s1"}'
```

SSE 消息体示例：

```json
{
  "session_id": "s1",
  "trace_id": "t1",
  "event": {
    "agent": "demo-echo",
    "type": "llm_response",
    "data": {}
  }
}
```

---

## 6. 双向通道（WS）与 HITL

WebSocket 地址：`/api/v1/agents/{name}:{version}/ws`

- `action=run`：启动可挂起运行（内部走 `Runner.run_with_checkpoint`）
- `action=resume`：提交人工输入恢复（内部走 `Runner.resume`）

`resume` 支持 `idempotency_key` 防重。

`run` 消息体示例：

```json
{
  "action": "run",
  "authorization": "Bearer <token>",
  "input": "请审批",
  "user_id": "u1",
  "session_id": "s1"
}
```

---

## 7. 会话与回放

```bash
# 列出会话（可选按状态过滤）
agenthub session list
agenthub session list --status suspended

# 查询会话
agenthub session get <session_id>

# 回放事件
agenthub trace <session_id>

# 恢复会话
agenthub session resume <session_id> --input "yes"

# 终止会话
agenthub session terminate <session_id>
```

REST 对应接口：

- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `GET /api/v1/sessions/{session_id}/events`
- `POST /api/v1/sessions/{session_id}/resume`
- `DELETE /api/v1/sessions/{session_id}`

## 8. 鉴权说明

当前仅支持 Bearer 头：

```http
Authorization: Bearer <token>
```

---

## 9. 运维与观测

- 健康检查：`GET /healthz`
- 指标：`GET /metrics`（Prometheus 文本格式）
- Playground：`GET /playground`
