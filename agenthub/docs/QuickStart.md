# AgentHub 快速入门

> 本文档基于当前代码实现（发行包：`ni.agenthub==0.1.0`，运行命令：`agenthub`）。

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
entry: agenthub.demo_agent:create_agent
schema:
  type: object
  properties:
    input:
      type: string
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
```

REST 对应接口：

```http
POST /v1/agents/{name}/invoke?version={version_or_alias}
Content-Type: application/json
{
  "input": "...",
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
curl -N "http://127.0.0.1:8008/v1/agents/demo-echo/stream?input=你好&user_id=u1&session_id=s1"
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

WebSocket 地址：`/v1/ws`

- `action=run`：启动可挂起运行（内部走 `Runner.run_with_checkpoint`）
- `action=resume`：提交人工输入恢复（内部走 `Runner.resume`）

`resume` 支持 `idempotency_key` 防重。

---

## 7. 会话与回放

```bash
# 查询会话
agenthub session <session_id>

# 回放事件
agenthub trace <session_id>

# 恢复会话
agenthub session <session_id> --resume "yes"

# 终止会话
agenthub session <session_id> --terminate
```

REST 对应接口：

- `GET /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `GET /v1/sessions/{session_id}/events`
- `POST /v1/sessions/{session_id}/resume`
- `POST /v1/sessions/{session_id}/terminate`

---

## 8. 运维与观测

- 健康检查：`GET /healthz`
- 指标：`GET /metrics`（Prometheus 文本格式）
- Playground：`GET /playground`
