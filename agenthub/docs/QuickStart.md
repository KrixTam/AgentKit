# AgentHub 快速入门

> 本文档基于当前代码实现（发行包：`ni.agenthub==0.3.4`，运行命令：`agenthub`）。

***

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

***

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
# 可选：默认应用到该 Agent 的 ModelCosplay（仅对开启能力的 Agent 生效）
# model_cosplay: "gpt-4o-mini"
tags: [demo, stable]
```

`entry` 必须是 `module:attr` 格式；若校验失败，服务端会返回字段级错误信息。
当 `agent.yaml` 配置了 `model_cosplay` 时，Hub 会在实例化该 Agent 后默认应用该配置；如果调用请求中也传入了 `model_cosplay`，则请求参数优先。
上述示例可直接用（将 `agent.yaml.example` 重命名/复制为 `agent.yaml` 后可注册并调用）。

***

## 3. 注册与发现

```bash
# 注册并打上别名
agenthub register ./agent.yaml --alias stable --alias latest

# 列出所有 Agent 版本
agenthub list

# 查看指定 Agent
agenthub info demo-echo
```

***

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

***

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

***

## 6. 双向通道（WS）与 HITL

WebSocket 地址：`/api/v1/agents/{name}:{version}/ws`

- `action=run`：启动可挂起运行（内部走 `Runner.run_with_checkpoint`）
- `action=resume`：提交人工输入恢复（内部走 `Runner.resume`）

`resume` 支持 `suspension_id` 精准恢复（多挂起场景）和 `idempotency_key` 防重。

`run` 消息体示例：

```json
{
  "action": "run",
  "authorization": "Bearer <token>",
  "input": "请审批",
  "model_cosplay": "gpt-4o-mini",
  "user_id": "u1",
  "session_id": "s1"
}
```

***

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

补充说明：当同一会话存在多个 pending 挂起点时，`resume`/`submit` 建议传 `suspension_id` 精准恢复；`GET /api/v1/hitl/{session_id}/form` 也支持同名 query 参数按挂起点读取表单。

## 8. 鉴权说明

当前仅支持 Bearer 头：

```http
Authorization: Bearer <token>
```

***

## 9. 运维与观测

- 健康检查：`GET /healthz`
- 指标：`GET /metrics`（Prometheus 文本格式）
- Playground：`GET /playground`（内置控制台，支持 Bearer 鉴权配置、Registry 注册/查询、Invoke、SSE、Session Events、HITL 提交）
- 审计日志（结构化 JSON）：包含 `db_ops`、`event_write_ms`、`agent_resolve_ms`，用于衡量单请求存储与解析开销

***

## 10. Playground 体验指南

Playground 是 AgentHub 内置的可视化联调控制台。你可以通过浏览器访问 `http://127.0.0.1:8008/playground` 体验全流程。

### 步骤 1：检查连接与健康

1. 打开浏览器访问 `/playground`。
2. 左上角“连接配置”区域，点击 **“检查健康”**。
3. 若右上角“响应”卡片返回 `{"status": "ok"}`，说明连接正常。

### 步骤 2：注册 Agent 目标

如果 AgentHub 使用 `memory` 模式启动，默认是没有 Agent 的。我们需要先注册一个测试 Agent。

1. 定位到左侧的 **“Registry 快捷操作”** 卡片。
2. 在 **Manifest JSON** 框中，输入或粘贴一个合法的 Agent 描述，例如基于 Ollama 的示例：
   ```json
   {
     "name": "demo-agent",
     "version": "0.1.0",
     "description": "测试Agent",
     "entry": "agentkit.examples.ollama.01_basic_chat:agent"
   }
   ```
   > 提示：`entry` 必须指向一个本地环境中确实存在的合法的 AgentKit Agent 实例（需确保你的执行环境里能 `import agentkit.examples.ollama`）。
3. 点击 **“注册”** 按钮。
4. 点击 **“列出 Agents”**，在右上角“响应”区确认注册成功。

### 步骤 3：发起同步 Invoke 调用

1. 在左侧中间的 **“Agent 目标”** 卡片中。
2. 确认 **Agent 名称** 是刚才注册的 `demo-agent`（如果使用版本，可以填 `demo-agent:0.1.0`）。
3. 在 **输入文本** 中填入想测试的话，比如“你好”。
4. 点击 **“同步 Invoke”** 按钮。
5. 等待请求完成后，右上角“响应”区会展示包含 `run_result` 和 `session_id` 的结果，并且会自动捕获生成的 `session_id` 到下方的输入框中。

### 步骤 4：体验 SSE Stream 流式调用

1. 再次修改 **输入文本**。
2. 点击 **“SSE Stream”** 按钮。
3. 右上角会自动切换到 **“事件流”** 标签，你将看到一行行由 AgentKit 发出的实时事件数据流。

### 步骤 5：会话与事件查询

1. 先确认你至少完成过一次成功调用（同步 Invoke 或 SSE），并且左侧 `session_id` 输入框里有本次调用返回的有效值（为空时请先重新发起一次调用）。
2. 点击右侧面板上方的 **“会话”** 标签。
3. 点击 **“查询 Session”** 或 **“查询 Events”** 查看结果；若返回 `{}` 或空列表，优先检查 `session_id` 是否完整、该次调用是否成功返回、以及当前查询是否命中同一运行中的网关实例与会话存储。

### 步骤 6：体验 HITL (Human In The Loop) 挂起与恢复

你可以使用两种方式体验 HITL：
推荐演示顺序：先执行 **方案 B（确定性触发）** 验证完整链路，再执行 **方案 A（LLM 工具调用触发）** 体验真实业务形态。

#### 方案 A：LLM 工具调用触发（高概率）

1. 回到左侧 **“Registry 快捷操作”** 卡片，将 **Manifest JSON** 改为如下内容并点击 **“注册”**：
   ```json
   {
     "name": "demo-hitl-agent",
     "version": "0.1.0",
     "description": "HITL 示例 Agent",
     "entry": "agentkit.examples.ollama.05_human_in_the_loop:agent"
   }
   ```
2. 点击 **“列出 Agents”**，确认 `demo-hitl-agent` 注册成功（若失败，优先检查 `entry` 是否可 import）。
3. 在左侧中间 **“Agent 目标”** 卡片里，将 **Agent 名称** 设置为 `demo-hitl-agent`（或 `demo-hitl-agent:0.1.0`）。
4. 本示例默认请将 **model_cosplay** 留空（`demo-hitl-agent` 未开启 ModelCosplay，填写会返回 400）；如需覆盖模型，请改用已开启 ModelCosplay 的 Agent，再填写例如 `ollama/qwen3.5:4b`。
5. 在 **输入文本** 填入“明确要求执行敏感操作”的请求（例如“请执行重启生产数据库”），然后点击 **“SSE Stream”**。
6. 右侧切换到 **“事件流”** 后，先确认出现 `tool_call`（`tool=confirm_action`）；随后应出现 `suspend_requested`，并自动填充 `suspension_id`。
7. 若未出现 `suspend_requested` 而直接 `final_output`，通常表示本轮没有触发工具调用：请改用更明确的操作指令重新发起，或更换为工具调用能力更稳定的模型后重试。
8. 在左侧 **“HITL 操作”** 卡片中点击 **“列出挂起会话”**，确认能看到与当前 `suspension_id` 对应的待处理任务。
9. 点击 **“获取表单”**；若返回“找不到上下文快照”，先检查左侧 `session_id` 与 `suspension_id` 是否来自同一次 `suspend_requested`，且中间未重新发起新会话或重启网关进程（`memory` 模式重启后会丢失挂起上下文）。
10. 在 **resume 输入** 填入恢复数据（例如 `reject`；若表单要求 JSON，则按表单字段填写）后点击 **“提交 HITL / Resume”**；成功时右侧会返回恢复后的新事件/最终结果，失败时优先按第 9 步重新核对 `session_id`、`suspension_id` 与当前实例一致性。

#### 方案 B：确定性触发（必现）

1. 在 **Manifest JSON** 中注册一个“确定性挂起”Agent：
   ```json
   {
     "name": "demo-hitl-deterministic",
     "version": "0.1.0",
     "description": "HITL 确定性示例 Agent",
     "entry": "agentkit.examples.ollama.19_hitl_deterministic:agent"
   }
   ```
2. 点击 **“注册”** 和 **“列出 Agents”**，确认 `demo-hitl-deterministic` 已可用。
3. 在 **Agent 名称** 填入 `demo-hitl-deterministic`，输入任意文本后点击 **“SSE Stream”**。
4. 此方案首轮会固定产出 `suspend_requested`，并自动填充 `suspension_id`（不依赖模型是否调用工具）。
5. 出现挂起后不要再点击 **“SSE Stream”** 或 **“同步 Invoke”**；请直接使用当前这次挂起对应的 `session_id` + `suspension_id` 执行恢复。
6. 点击 **“列出挂起会话”** 与 **“获取表单”**，确认待处理挂起任务。
7. 在 **resume 输入** 中填入 `approve`（或 `reject`），点击 **“提交 HITL / Resume”**，右侧会输出恢复后的 `final_output`，完成闭环。
