from __future__ import annotations

import copy
import json
import logging
import os
import time
import uuid
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Header, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse

from agentkit.runner.events import Event
from agentkit.runner.runner import Runner

from .auth import authenticate_request
from .config import HubConfig
from .models import ApiResponse, InvokeRequest, RegisterRequest, ResumeRequest, SessionStatus
from .runtime import (
    apply_model_cosplay,
    HubContextStore,
    Metrics,
    QuotaManager,
    append_event_only,
    ensure_session,
    load_entry,
    resolve_session_status,
)
from .stores.base import RegistryStore, SessionStore
from .stores.memory import InMemoryRegistryStore, InMemorySessionStore
from .stores.sqlite import SQLiteRegistryStore, SQLiteSessionStore

logger = logging.getLogger("agenthub.gateway")


def _json_error(code: int, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=ApiResponse(code=code, message=message, data=None).model_dump())


def _structured_audit(action: str, **kwargs: Any) -> None:
    payload = {"action": action, "timestamp": time.time(), **kwargs}
    logger.info(json.dumps(payload, ensure_ascii=False))


def _parse_name_version(name_or_pair: str, version: str | None = None) -> tuple[str, str | None]:
    if ":" in name_or_pair:
        name, parsed_version = name_or_pair.rsplit(":", 1)
        return name, parsed_version
    return name_or_pair, version


def _build_stores(config: HubConfig) -> tuple[RegistryStore, SessionStore]:
    if config.store_type == "memory":
        logger.warning("AgentHub 当前使用内存存储模式，重启后数据将丢失。")
        return InMemoryRegistryStore(), InMemorySessionStore()
    os.makedirs(os.path.dirname(config.sqlite_path) or ".", exist_ok=True)
    return SQLiteRegistryStore(config.sqlite_path), SQLiteSessionStore(config.sqlite_path)


def create_app(config: HubConfig | None = None) -> FastAPI:
    cfg = config or HubConfig.from_env()
    registry_store, session_store = _build_stores(cfg)
    context_store = HubContextStore(session_store)
    metrics = Metrics()
    quota = QuotaManager(cfg.max_concurrency_per_user, cfg.rate_limit_per_minute)

    app = FastAPI(title="AgentHub", version="0.1.0")
    _agent_prototype_cache: dict[tuple[str, str, str], Any] = {}

    def _new_obs() -> dict[str, float]:
        return {"db_ops": 0.0, "event_write_ms": 0.0, "agent_resolve_ms": 0.0}

    def _add_db_ops(obs: dict[str, float], count: int = 1) -> None:
        obs["db_ops"] += float(count)

    def _auth(authorization: str | None) -> dict[str, Any]:
        return authenticate_request(cfg, authorization=authorization)

    def _quota_key(user_id: str | None, tenant_id: str | None) -> str:
        return f"{tenant_id or 'default'}:{user_id or 'anonymous'}"

    def _clear_agent_cache() -> None:
        _agent_prototype_cache.clear()

    def _clone_agent_instance(prototype: Any) -> Any:
        if hasattr(prototype, "model_copy"):
            return prototype.model_copy(deep=True)
        return copy.deepcopy(prototype)

    def _resolve_agent_instance(name: str, version_or_alias: str | None):
        manifest = registry_store.resolve(name, version_or_alias)
        if not manifest:
            raise ValueError(f"agent_not_found:{name}:{version_or_alias or 'latest'}")
        cache_key = (manifest.name, manifest.version, manifest.entry)
        prototype = _agent_prototype_cache.get(cache_key)
        if prototype is None:
            prototype = load_entry(manifest.entry)
            _agent_prototype_cache[cache_key] = prototype
        return manifest, _clone_agent_instance(prototype)

    def _resolve_agent_instance_observed(name: str, version_or_alias: str | None, obs: dict[str, float]):
        _add_db_ops(obs, 1)
        start = time.perf_counter()
        manifest, agent = _resolve_agent_instance(name, version_or_alias)
        obs["agent_resolve_ms"] += (time.perf_counter() - start) * 1000.0
        return manifest, agent

    def _effective_model_cosplay(manifest: Any, request_model_cosplay: Any) -> Any:
        if request_model_cosplay not in (None, ""):
            return request_model_cosplay
        return getattr(manifest, "model_cosplay", None)

    def _append_event_observed(obs: dict[str, float], session_id: str, event: Event) -> None:
        obs["event_write_ms"] += append_event_only(session_store, session_id, event)
        _add_db_ops(obs, 1)

    def _append_events_observed(obs: dict[str, float], session_id: str, events: list[Event]) -> None:
        if not events:
            return
        start = time.perf_counter()
        session_store.append_events(session_id, [e.to_dict() for e in events])
        obs["event_write_ms"] += (time.perf_counter() - start) * 1000.0
        _add_db_ops(obs, len(events))

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "store": cfg.store_type}

    @app.get("/.well-known/appspecific/com.chrome.devtools.json")
    async def chrome_devtools_probe():
        # Some browser tooling probes this path; return a harmless empty payload.
        return {}

    @app.get("/metrics")
    async def metrics_endpoint():
        return PlainTextResponse(metrics.to_prometheus(), media_type="text/plain; version=0.0.4")

    @app.get("/playground")
    async def playground():
        html = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AgentHub Playground</title>
  <style>
    :root {
      --bg: #0b1020;
      --panel: #121a31;
      --panel2: #182241;
      --text: #e7ecff;
      --muted: #9aa7d2;
      --accent: #5fa8ff;
      --ok: #2bc48a;
      --warn: #ffcc66;
      --bad: #ff6b6b;
      --border: #2b3762;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; overflow: hidden; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.4 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
    }
    .wrap {
      max-width: 1260px;
      margin: 0 auto;
      padding: 16px;
      height: 100vh;
      height: 100dvh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    h1 { margin: 0 0 8px; font-size: 20px; }
    .muted { color: var(--muted); }
    .grid {
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 12px;
      flex: 1;
      min-height: 0;
      overflow: hidden;
      margin-top: 16px;
    }
    .left-pane {
      height: 100%;
      overflow-y: auto;
      padding-right: 4px;
    }
    .right-pane {
      height: 100%;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .right-pane > .card {
      flex: 1;
      margin-bottom: 0;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }
    .left-pane::-webkit-scrollbar { width: 10px; }
    .left-pane::-webkit-scrollbar-thumb {
      background: #2a3b71;
      border-radius: 999px;
    }
    .left-pane::-webkit-scrollbar-track { background: transparent; }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 10px;
    }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    label { display: block; margin: 8px 0 4px; color: var(--muted); font-size: 12px; }
    input, textarea, select, button {
      width: 100%;
      background: var(--panel2);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      font: inherit;
    }
    textarea { min-height: 92px; resize: vertical; }
    button {
      cursor: pointer;
      background: #20346b;
      border-color: #3153a8;
    }
    button:hover { filter: brightness(1.08); }
    .btns { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 8px; }
    .btn-wide { grid-column: 1 / -1; }
    .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .chip {
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      color: var(--muted);
    }
    .chip.ok { color: var(--ok); border-color: #1e6f53; }
    .chip.warn { color: var(--warn); border-color: #8d6e2f; }
    .chip.bad { color: var(--bad); border-color: #8a2f2f; }
    pre {
      margin: 0;
      background: #0a1228;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      min-height: 280px;
      height: 100%;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .title { margin: 0 0 8px; font-size: 14px; color: var(--muted); }
    .tiny { font-size: 12px; color: var(--muted); }
    .tabs { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 8px; }
    .tab {
      width: auto;
      padding: 6px 10px;
      border-radius: 999px;
      background: #182449;
      color: var(--muted);
    }
    .tab.active { background: #244291; color: #fff; }
    .section { display: none; }
    .section.active {
      display: block;
      flex: 1;
      min-height: 0;
      overflow: auto;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>AgentHub Playground</h1>
    <div class="muted">面向联调的控制台：鉴权、注册、Invoke、SSE、会话事件与 HITL 恢复</div>
    <div class="grid">
      <div class="left-pane">
        <div class="card">
          <div class="title">连接配置</div>
          <label>Base URL</label>
          <input id="baseUrl" value="" />
          <label>Bearer Token（可选）</label>
          <input id="token" type="password" placeholder="留空表示不带鉴权头" />
          <div class="btns">
            <button onclick="saveSettings()">保存配置</button>
            <button onclick="checkHealth()">检查健康</button>
          </div>
          <div class="chips">
            <span class="chip" id="statusChip">未连接</span>
            <span class="chip" id="latencyChip">-</span>
            <span class="chip" id="sessionChip">session: -</span>
            <span class="chip" id="suspensionChip">suspension: -</span>
          </div>
        </div>

        <div class="card">
          <div class="title">Registry 快捷操作</div>
          <label>Manifest JSON</label>
          <textarea id="manifestJson" placeholder='{"name":"demo-agent","version":"0.1.0","entry":"pkg.mod:agent"}'>{
  "name": "demo-agent",
  "version": "0.1.0",
  "description": "测试Agent",
  "entry": "agentkit.examples.ollama.01_basic_chat:agent"
}</textarea>
          <label>aliases（逗号分隔，可选）</label>
          <input id="aliases" placeholder="latest,stable" />
          <div class="btns">
            <button onclick="registerAgent()">注册</button>
            <button onclick="listAgents()">列出 Agents</button>
          </div>
        </div>

        <div class="card">
          <div class="title">Agent 目标</div>
          <label>Agent 名称或 name:version</label>
          <input id="nameVersion" value="demo-agent" />
          <label>输入文本</label>
          <textarea id="inputText">你好</textarea>
          <div class="row">
            <div>
              <label>user_id（可选）</label>
              <input id="userId" />
            </div>
            <div>
              <label>session_id（可选）</label>
              <input id="sessionId" />
            </div>
          </div>
          <div class="row">
            <div>
              <label>model_cosplay（可选）</label>
              <input id="modelCosplay" placeholder="如 ollama/qwen3.5:cloud" />
            </div>
            <div>
              <label>max_turns（默认 10）</label>
              <input id="maxTurns" type="number" value="10" min="1" />
            </div>
          </div>
          <div class="btns">
            <button onclick="invoke()">同步 Invoke</button>
            <button onclick="startStream()">SSE Stream</button>
            <button onclick="stopStream()" class="btn-wide">停止 Stream</button>
          </div>
        </div>

        <div class="card">
          <div class="title">HITL 操作</div>
          <label>resume 输入</label>
          <textarea id="resumeInput">approve</textarea>
          <label>suspension_id（可选）</label>
          <input id="resumeSuspensionId" placeholder="留空则使用最新捕获值" />
          <div class="btns">
            <button onclick="listSuspended()">列出挂起会话</button>
            <button onclick="getHitlForm()">获取表单</button>
            <button onclick="submitHitl()" class="btn-wide">提交 HITL / Resume</button>
          </div>
        </div>
      </div>

      <div class="right-pane">
        <div class="card">
          <div class="tabs">
            <button class="tab active" data-tab="response" onclick="switchTab('response')">响应</button>
            <button class="tab" data-tab="events" onclick="switchTab('events')">事件流</button>
            <button class="tab" data-tab="session" onclick="switchTab('session')">会话</button>
            <button class="tab" data-tab="request" onclick="switchTab('request')">请求快照</button>
          </div>

          <div id="tab-response" class="section active">
            <pre id="responseOut">{}</pre>
          </div>
          <div id="tab-events" class="section">
            <pre id="eventOut">等待流式事件...</pre>
          </div>
          <div id="tab-session" class="section">
            <div class="btns" style="margin-bottom:8px">
              <button onclick="getSession()">查询 Session</button>
              <button onclick="getSessionEvents()">查询 Events</button>
            </div>
            <pre id="sessionOut">{}</pre>
          </div>
          <div id="tab-request" class="section">
            <div class="tiny">最近一次请求（method / path / payload）</div>
            <pre id="requestOut">{}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let streamController = null;
    let currentSessionId = "";
    let currentSuspensionId = "";

    const byId = (id) => document.getElementById(id);
    const setJson = (id, data) => byId(id).textContent = JSON.stringify(data, null, 2);

    function nowBaseUrl() {
      const raw = byId("baseUrl").value.trim();
      return raw || window.location.origin;
    }

    function authHeaders(jsonBody = true) {
      const h = {};
      if (jsonBody) h["Content-Type"] = "application/json";
      const token = byId("token").value.trim();
      if (token) h["Authorization"] = `Bearer ${token}`;
      return h;
    }

    function setStatus(kind, text) {
      const chip = byId("statusChip");
      chip.className = "chip";
      if (kind === "ok") chip.classList.add("ok");
      if (kind === "warn") chip.classList.add("warn");
      if (kind === "bad") chip.classList.add("bad");
      chip.textContent = text;
    }

    function setLatency(ms) {
      byId("latencyChip").textContent = `latency: ${ms.toFixed(1)} ms`;
    }

    function updateSessionHint(sessionId, suspensionId) {
      if (sessionId) currentSessionId = sessionId;
      if (suspensionId) currentSuspensionId = suspensionId;
      byId("sessionChip").textContent = `session: ${currentSessionId || "-"}`;
      byId("suspensionChip").textContent = `suspension: ${currentSuspensionId || "-"}`;
      if (currentSessionId) byId("sessionId").value = currentSessionId;
      if (currentSuspensionId) byId("resumeSuspensionId").value = currentSuspensionId;
    }

    function saveSettings() {
      localStorage.setItem("agenthub_base_url", byId("baseUrl").value.trim());
      localStorage.setItem("agenthub_token", byId("token").value.trim());
      setStatus("ok", "配置已保存");
    }

    function loadSettings() {
      byId("baseUrl").value = localStorage.getItem("agenthub_base_url") || window.location.origin;
      byId("token").value = localStorage.getItem("agenthub_token") || "";
    }

    function switchTab(name) {
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
      document.querySelector(`[data-tab="${name}"]`).classList.add("active");
      document.querySelectorAll(".section").forEach((x) => x.classList.remove("active"));
      byId(`tab-${name}`).classList.add("active");
    }

    async function api(method, path, payload = null, opts = {}) {
      const reqSnapshot = { method, path, payload };
      setJson("requestOut", reqSnapshot);
      const start = performance.now();
      const resp = await fetch(`${nowBaseUrl()}${path}`, {
        method,
        headers: authHeaders(payload !== null),
        body: payload === null ? null : JSON.stringify(payload),
        signal: opts.signal || null,
      });
      const elapsed = performance.now() - start;
      setLatency(elapsed);

      let body = null;
      try {
        body = await resp.json();
      } catch (_) {
        body = { code: resp.status, message: "non-json response" };
      }
      return { ok: resp.ok, status: resp.status, body };
    }

    function buildInvokePayload() {
      const sessionId = byId("sessionId").value.trim();
      const maxTurns = parseInt(byId("maxTurns").value || "10", 10);
      const payload = {
        input: byId("inputText").value,
        user_id: byId("userId").value.trim() || null,
        session_id: sessionId || null,
        model_cosplay: byId("modelCosplay").value.trim() || null,
        max_turns: Number.isFinite(maxTurns) ? maxTurns : 10,
      };
      return payload;
    }

    async function checkHealth() {
      try {
        const r = await api("GET", "/healthz");
        setJson("responseOut", r.body);
        setStatus(r.ok ? "ok" : "bad", r.ok ? "健康检查通过" : `健康检查失败(${r.status})`);
        switchTab("response");
      } catch (e) {
        setStatus("bad", `连接异常: ${e.message}`);
      }
    }

    async function invoke() {
      const nameVersion = encodeURIComponent(byId("nameVersion").value.trim());
      const r = await api("POST", `/api/v1/agents/${nameVersion}/invoke`, buildInvokePayload());
      setJson("responseOut", r.body);
      const sid = r.body?.data?.session_id;
      if (sid) {
        updateSessionHint(sid, null);
      }
      setStatus(r.ok ? "ok" : "bad", r.ok ? "Invoke 成功" : `Invoke 失败(${r.status})`);
      switchTab("response");
    }

    async function startStream() {
      stopStream();
      byId("eventOut").textContent = "";
      const nameVersion = encodeURIComponent(byId("nameVersion").value.trim());
      const payload = buildInvokePayload();
      const reqSnapshot = { method: "POST", path: `/api/v1/agents/${nameVersion}/stream`, payload };
      setJson("requestOut", reqSnapshot);
      switchTab("events");
      streamController = new AbortController();
      setStatus("warn", "SSE 连接中");

      const start = performance.now();
      let resp;
      try {
        resp = await fetch(`${nowBaseUrl()}/api/v1/agents/${nameVersion}/stream`, {
          method: "POST",
          headers: authHeaders(true),
          body: JSON.stringify(payload),
          signal: streamController.signal,
        });
      } catch (e) {
        setStatus("bad", `SSE 建立失败: ${e.message}`);
        return;
      }
      setLatency(performance.now() - start);
      if (!resp.ok || !resp.body) {
        const txt = await resp.text();
        byId("eventOut").textContent = `SSE 建立失败: ${resp.status}\\n${txt}`;
        setStatus("bad", `SSE 失败(${resp.status})`);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buf = "";
      setStatus("ok", "SSE 已连接");
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\\n");
        buf = lines.pop() || "";
        for (const raw of lines) {
          const line = raw.trim();
          if (!line.startsWith("data:")) continue;
          const payloadText = line.slice(5).trim();
          if (!payloadText) continue;
          try {
            const obj = JSON.parse(payloadText);
            const sid = obj.session_id;
            const event = obj.event || {};
            const suspensionId = event?.data?.suspension_id;
            updateSessionHint(sid, suspensionId || null);
            byId("eventOut").textContent += JSON.stringify(obj, null, 2) + "\\n";
          } catch (e) {
            byId("eventOut").textContent += payloadText + "\\n";
          }
        }
      }
      setStatus("warn", "SSE 已结束");
    }

    function stopStream() {
      if (streamController) {
        streamController.abort();
        streamController = null;
        setStatus("warn", "SSE 已停止");
      }
    }

    async function getSession() {
      const sid = byId("sessionId").value.trim() || currentSessionId;
      if (!sid) return setStatus("warn", "请先提供 session_id");
      const r = await api("GET", `/api/v1/sessions/${encodeURIComponent(sid)}`);
      setJson("sessionOut", r.body);
      setStatus(r.ok ? "ok" : "bad", r.ok ? "Session 获取成功" : `Session 获取失败(${r.status})`);
      switchTab("session");
    }

    async function getSessionEvents() {
      const sid = byId("sessionId").value.trim() || currentSessionId;
      if (!sid) return setStatus("warn", "请先提供 session_id");
      const r = await api("GET", `/api/v1/sessions/${encodeURIComponent(sid)}/events`);
      setJson("sessionOut", r.body);
      setStatus(r.ok ? "ok" : "bad", r.ok ? "Events 获取成功" : `Events 获取失败(${r.status})`);
      switchTab("session");
    }

    async function listSuspended() {
      const r = await api("GET", "/api/v1/hitl/suspended");
      setJson("responseOut", r.body);
      const list = r.body?.data || [];
      if (Array.isArray(list) && list.length > 0) {
        updateSessionHint(list[0].session_id, null);
      }
      setStatus(r.ok ? "ok" : "bad", r.ok ? "挂起会话已加载" : `查询失败(${r.status})`);
      switchTab("response");
    }

    async function getHitlForm() {
      const sid = byId("sessionId").value.trim() || currentSessionId;
      if (!sid) return setStatus("warn", "请先提供 session_id");
      const suspensionId = byId("resumeSuspensionId").value.trim() || currentSuspensionId;
      const query = suspensionId ? `?suspension_id=${encodeURIComponent(suspensionId)}` : "";
      const r = await api("GET", `/api/v1/hitl/${encodeURIComponent(sid)}/form${query}`);
      setJson("responseOut", r.body);
      setStatus(r.ok ? "ok" : "bad", r.ok ? "HITL 表单已获取" : `获取失败(${r.status})`);
      switchTab("response");
    }

    async function submitHitl() {
      const sid = byId("sessionId").value.trim() || currentSessionId;
      if (!sid) return setStatus("warn", "请先提供 session_id");
      const suspensionId = byId("resumeSuspensionId").value.trim() || currentSuspensionId || null;
      const payload = {
        user_input: byId("resumeInput").value,
        suspension_id: suspensionId,
      };
      const r = await api("POST", `/api/v1/hitl/${encodeURIComponent(sid)}/submit`, payload);
      setJson("responseOut", r.body);
      setStatus(r.ok ? "ok" : "bad", r.ok ? "HITL 提交成功" : `提交失败(${r.status})`);
      switchTab("response");
    }

    async function registerAgent() {
      let manifest = null;
      try {
        manifest = JSON.parse(byId("manifestJson").value || "{}");
      } catch (e) {
        setStatus("bad", `Manifest JSON 无效: ${e.message}`);
        return;
      }
      const aliases = byId("aliases").value.split(",").map((x) => x.trim()).filter(Boolean);
      const r = await api("POST", "/api/v1/registry/agents", { manifest, aliases });
      setJson("responseOut", r.body);
      setStatus(r.ok ? "ok" : "bad", r.ok ? "注册成功" : `注册失败(${r.status})`);
      switchTab("response");
    }

    async function listAgents() {
      const r = await api("GET", "/api/v1/registry/agents");
      setJson("responseOut", r.body);
      setStatus(r.ok ? "ok" : "bad", r.ok ? "Agents 已加载" : `查询失败(${r.status})`);
      switchTab("response");
    }

    loadSettings();
    checkHealth();
  </script>
</body>
</html>
"""
        return HTMLResponse(html)

    async def _register_impl(
        req: RegisterRequest,
        *,
        authorization: str | None,
    ):
        _auth(authorization)
        try:
            registry_store.register(req.manifest, req.aliases)
            _clear_agent_cache()
            _structured_audit("register_agent", agent=req.manifest.name, version=req.manifest.version)
            return ApiResponse(data={"name": req.manifest.name, "version": req.manifest.version})
        except Exception as e:
            return _json_error(1001, str(e), status_code=400)

    async def _list_agents_impl(authorization: str | None):
        _auth(authorization)
        return ApiResponse(data=[m.model_dump(by_alias=True) for m in registry_store.list_all()])

    async def _list_agent_versions_impl(name: str, authorization: str | None):
        _auth(authorization)
        return ApiResponse(data=[m.model_dump(by_alias=True) for m in registry_store.list_versions(name)])

    async def _unregister_impl(name: str, version: str, authorization: str | None):
        _auth(authorization)
        registry_store.unregister(name, version)
        _clear_agent_cache()
        _structured_audit("unregister_agent", agent=name, version=version)
        return ApiResponse(data={"name": name, "version": version, "status": "offline"})

    async def _invoke_impl(
        *,
        name: str,
        req: InvokeRequest,
        version: str | None,
        authorization: str | None,
        x_tenant_id: str | None,
    ):
        _auth(authorization)
        quota_key = _quota_key(req.user_id, x_tenant_id)
        start = time.time()
        session_status_for_metrics = SessionStatus.ERROR
        obs = _new_obs()
        try:
            quota.acquire(quota_key)
            try:
                manifest, agent = _resolve_agent_instance_observed(name, version, obs)
            except ValueError as e:
                if str(e).startswith("agent_not_found:"):
                    return _json_error(1004, str(e), status_code=404)
                raise
            try:
                agent = apply_model_cosplay(agent, _effective_model_cosplay(manifest, req.model_cosplay))
            except ValueError as e:
                return _json_error(1007, str(e), status_code=400)
            session = ensure_session(
                session_store,
                session_id=req.session_id,
                agent_name=manifest.name,
                agent_version=manifest.version,
                user_id=req.user_id,
                trace_id=req.trace_id or str(uuid.uuid4()),
                db_op_counter=lambda n: _add_db_ops(obs, n),
            )
            result = await Runner.run(
                agent,
                input=req.input,
                context=req.context,
                user_id=req.user_id,
                session_id=session.session_id,
                max_turns=req.max_turns,
            )
            _append_events_observed(obs, session.session_id, result.events)
            if result.success:
                session_store.update_status(session.session_id, SessionStatus.COMPLETED)
                _add_db_ops(obs, 1)
                session_status_for_metrics = SessionStatus.COMPLETED
            else:
                session_store.update_status(session.session_id, SessionStatus.ERROR, result.error)
                _add_db_ops(obs, 1)
                session_status_for_metrics = SessionStatus.ERROR
            _structured_audit(
                "invoke",
                session_id=session.session_id,
                agent=name,
                version=manifest.version,
                ok=result.success,
                db_ops=int(obs["db_ops"]),
                event_write_ms=round(obs["event_write_ms"], 3),
                agent_resolve_ms=round(obs["agent_resolve_ms"], 3),
            )
            return ApiResponse(
                data={
                    "session_id": session.session_id,
                    "trace_id": session.trace_id,
                    "run_result": {
                        "final_output": result.final_output,
                        "last_agent": result.last_agent,
                        "error": result.error,
                        "success": result.success,
                    },
                }
            )
        except Exception as e:
            logger.error(f"Invoke error: {e}", exc_info=True)
            session_status_for_metrics = SessionStatus.ERROR
            return _json_error(1003, str(e), status_code=500)
        finally:
            quota.release(quota_key)
            metrics.observe((time.time() - start) * 1000.0, session_status_for_metrics)

    async def _stream_impl(
        *,
        name: str,
        req: InvokeRequest,
        version: str | None,
        authorization: str | None,
    ):
        _auth(authorization)
        obs = _new_obs()
        try:
            manifest, agent = _resolve_agent_instance_observed(name, version, obs)
        except ValueError as e:
            if str(e).startswith("agent_not_found:"):
                return _json_error(1004, str(e), status_code=404)
            return _json_error(1003, str(e), status_code=500)
        try:
            agent = apply_model_cosplay(agent, _effective_model_cosplay(manifest, req.model_cosplay))
        except ValueError as e:
            return _json_error(1007, str(e), status_code=400)
        session = ensure_session(
            session_store,
            session_id=req.session_id,
            agent_name=manifest.name,
            agent_version=manifest.version,
            user_id=req.user_id,
            trace_id=req.trace_id or str(uuid.uuid4()),
            db_op_counter=lambda n: _add_db_ops(obs, n),
        )

        async def gen() -> AsyncGenerator[str, None]:
            stream_status = SessionStatus.RUNNING
            try:
                async for e in Runner.run_with_checkpoint(
                    agent,
                    input=req.input,
                    context=req.context,
                    context_store=context_store,
                    max_turns=req.max_turns,
                    user_id=req.user_id,
                    session_id=session.session_id,
                ):
                    _append_event_observed(obs, session.session_id, e)
                    next_status = resolve_session_status(e.type, stream_status)
                    if next_status != stream_status:
                        session_store.update_status(
                            session.session_id,
                            next_status,
                            str(e.data) if next_status == SessionStatus.ERROR else None,
                        )
                        _add_db_ops(obs, 1)
                        stream_status = next_status
                    payload = {"session_id": session.session_id, "trace_id": session.trace_id, "event": e.to_dict()}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except Exception as ex:
                err = Event(agent=name, type="error", data=str(ex))
                _append_event_observed(obs, session.session_id, err)
                session_store.update_status(session.session_id, SessionStatus.ERROR, str(ex))
                _add_db_ops(obs, 1)
                stream_status = SessionStatus.ERROR
                yield f"data: {json.dumps({'event': err.to_dict()}, ensure_ascii=False)}\n\n"
            finally:
                if stream_status == SessionStatus.RUNNING:
                    session_store.update_status(session.session_id, SessionStatus.EXPIRED, "sse_disconnected")
                    _add_db_ops(obs, 1)
                _structured_audit(
                    "stream",
                    session_id=session.session_id,
                    agent=name,
                    version=manifest.version,
                    status=stream_status.value,
                    db_ops=int(obs["db_ops"]),
                    event_write_ms=round(obs["event_write_ms"], 3),
                    agent_resolve_ms=round(obs["agent_resolve_ms"], 3),
                )

        return StreamingResponse(gen(), media_type="text/event-stream")

    async def _resume_impl(
        *,
        session_id: str,
        req: ResumeRequest,
        authorization: str | None,
    ):
        _auth(authorization)
        obs = _new_obs()
        session = session_store.get(session_id)
        _add_db_ops(obs, 1)
        if not session:
            return _json_error(1004, f"session_not_found:{session_id}", 404)
        if req.idempotency_key and session.metadata.get("last_resume_key") == req.idempotency_key:
            return ApiResponse(data={"session_id": session_id, "status": "duplicate_ignored"})
        if req.idempotency_key:
            session.metadata["last_resume_key"] = req.idempotency_key
        manifest, agent = _resolve_agent_instance_observed(session.agent_name, session.agent_version, obs)
        try:
            agent = apply_model_cosplay(agent, _effective_model_cosplay(manifest, None))
        except ValueError as e:
            return _json_error(1007, str(e), status_code=400)
        events: list[dict[str, Any]] = []
        current_status = session.status
        async for e in Runner.resume(
            agent,
            session_id=session_id,
            user_input=req.user_input,
            context_store=context_store,
            suspension_id=req.suspension_id,
            idempotency_key=req.idempotency_key,
        ):
            _append_event_observed(obs, session_id, e)
            current_status = resolve_session_status(e.type, current_status)
            events.append(e.to_dict())
        if current_status != session.status:
            session_store.update_status(
                session_id,
                current_status,
                str(events[-1].get("data")) if current_status == SessionStatus.ERROR and events else None,
            )
            _add_db_ops(obs, 1)
        _structured_audit(
            "resume",
            session_id=session_id,
            status=current_status.value,
            db_ops=int(obs["db_ops"]),
            event_write_ms=round(obs["event_write_ms"], 3),
            agent_resolve_ms=round(obs["agent_resolve_ms"], 3),
        )
        return ApiResponse(data={"session_id": session_id, "events": events})

    async def _terminate_impl(
        *,
        session_id: str,
        authorization: str | None,
    ):
        _auth(authorization)
        session_store.terminate(session_id)
        _structured_audit("terminate_session", session_id=session_id)
        return ApiResponse(data={"session_id": session_id, "status": "terminated"})

    async def _ws_handler(
        ws: WebSocket,
        *,
        fixed_agent_name: str | None = None,
        fixed_version: str | None = None,
    ) -> None:
        await ws.accept()
        active_sessions: set[str] = set()
        try:
            while True:
                text = await ws.receive_text()
                msg = json.loads(text)
                action = msg.get("action", "run")
                authz = msg.get("authorization")
                _auth(authz)
                if action == "run":
                    obs = _new_obs()
                    agent_name = fixed_agent_name or msg["agent"]
                    version = fixed_version if fixed_agent_name else msg.get("version")
                    try:
                        manifest, agent = _resolve_agent_instance_observed(agent_name, version, obs)
                    except ValueError as e:
                        await ws.send_json({"error": str(e)})
                        continue
                    try:
                        agent = apply_model_cosplay(agent, _effective_model_cosplay(manifest, msg.get("model_cosplay")))
                    except ValueError as e:
                        await ws.send_json({"error": str(e)})
                        continue
                    session = ensure_session(
                        session_store,
                        session_id=msg.get("session_id"),
                        agent_name=manifest.name,
                        agent_version=manifest.version,
                        user_id=msg.get("user_id"),
                        trace_id=msg.get("trace_id") or str(uuid.uuid4()),
                        db_op_counter=lambda n: _add_db_ops(obs, n),
                    )
                    async for e in Runner.run_with_checkpoint(
                        agent,
                        input=msg["input"],
                        session_id=session.session_id,
                        context_store=context_store,
                        user_id=msg.get("user_id"),
                        max_turns=msg.get("max_turns", 10),
                    ):
                        _append_event_observed(obs, session.session_id, e)
                        ws_status = resolve_session_status(e.type, SessionStatus.RUNNING)
                        if ws_status != SessionStatus.RUNNING:
                            session_store.update_status(
                                session.session_id,
                                ws_status,
                                str(e.data) if ws_status == SessionStatus.ERROR else None,
                            )
                            _add_db_ops(obs, 1)
                        active_sessions.add(session.session_id)
                        await ws.send_json({"session_id": session.session_id, "trace_id": session.trace_id, "event": e.to_dict()})
                    _structured_audit(
                        "ws_run",
                        session_id=session.session_id,
                        agent=agent_name,
                        version=manifest.version,
                        db_ops=int(obs["db_ops"]),
                        event_write_ms=round(obs["event_write_ms"], 3),
                        agent_resolve_ms=round(obs["agent_resolve_ms"], 3),
                    )
                elif action == "resume":
                    obs = _new_obs()
                    session_id = msg["session_id"]
                    session = session_store.get(session_id)
                    _add_db_ops(obs, 1)
                    if not session:
                        await ws.send_json({"error": f"session_not_found:{session_id}"})
                        continue
                    manifest, agent = _resolve_agent_instance_observed(session.agent_name, session.agent_version, obs)
                    try:
                        agent = apply_model_cosplay(agent, _effective_model_cosplay(manifest, None))
                    except ValueError as e:
                        await ws.send_json({"error": str(e)})
                        continue
                    idempotency_key = msg.get("idempotency_key")
                    if idempotency_key and session.metadata.get("last_resume_key") == idempotency_key:
                        await ws.send_json({"session_id": session_id, "status": "duplicate_ignored"})
                        continue
                    if idempotency_key:
                        session.metadata["last_resume_key"] = idempotency_key
                    async for e in Runner.resume(
                        agent,
                        session_id=session_id,
                        user_input=msg["user_input"],
                        context_store=context_store,
                        suspension_id=msg.get("suspension_id"),
                        idempotency_key=idempotency_key,
                    ):
                        _append_event_observed(obs, session_id, e)
                        next_status = resolve_session_status(e.type, session.status)
                        if next_status != session.status:
                            session_store.update_status(
                                session_id,
                                next_status,
                                str(e.data) if next_status == SessionStatus.ERROR else None,
                            )
                            _add_db_ops(obs, 1)
                            session.status = next_status
                        active_sessions.add(session_id)
                        await ws.send_json({"session_id": session_id, "event": e.to_dict()})
                    _structured_audit(
                        "ws_resume",
                        session_id=session_id,
                        status=session.status.value,
                        db_ops=int(obs["db_ops"]),
                        event_write_ms=round(obs["event_write_ms"], 3),
                        agent_resolve_ms=round(obs["agent_resolve_ms"], 3),
                    )
                else:
                    await ws.send_json({"error": f"unknown_action:{action}"})
        except WebSocketDisconnect:
            for sid in active_sessions:
                session = session_store.get(sid)
                if session and session.status == SessionStatus.RUNNING:
                    session_store.update_status(sid, SessionStatus.EXPIRED, "ws_disconnected")
            return

    # SRS /api/v1 registry endpoints
    @app.post("/api/v1/registry/agents")
    async def api_register_agents(
        req: RegisterRequest,
        authorization: str | None = Header(default=None),
    ):
        return await _register_impl(req, authorization=authorization)

    @app.get("/api/v1/registry/agents")
    async def api_list_registry_agents(
        authorization: str | None = Header(default=None),
    ):
        return await _list_agents_impl(authorization)

    @app.post("/api/v1/registry/agents/{name}/aliases/{alias}")
    async def api_set_alias(
        name: str,
        alias: str,
        version: str = Query(...),
        authorization: str | None = Header(default=None),
    ):
        _auth(authorization)
        try:
            registry_store.set_alias(name, alias, version)
            _clear_agent_cache()
            return ApiResponse(data={"name": name, "alias": alias, "version": version})
        except Exception as e:
            return _json_error(1002, str(e))

    @app.get("/api/v1/registry/agents/{name}")
    async def api_get_registry_agent(
        name: str,
        authorization: str | None = Header(default=None),
    ):
        return await _list_agent_versions_impl(name, authorization)

    @app.delete("/api/v1/registry/agents/{name_version}")
    async def api_delete_registry_agent(
        name_version: str,
        authorization: str | None = Header(default=None),
    ):
        name, version = _parse_name_version(name_version)
        if not version:
            return _json_error(1006, "invalid_name_version_format: expected name:version", 400)
        return await _unregister_impl(name, version, authorization)

    # SRS /api/v1 invoke & stream endpoints
    @app.post("/api/v1/agents/{name_version}/invoke")
    async def api_invoke_agent(
        name_version: str,
        req: InvokeRequest,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        name, version = _parse_name_version(name_version)
        return await _invoke_impl(
            name=name,
            req=req,
            version=version,
            authorization=authorization,
            x_tenant_id=x_tenant_id,
        )

    @app.post("/api/v1/agents/{name_version}/stream")
    async def api_stream_agent(
        name_version: str,
        req: InvokeRequest,
        authorization: str | None = Header(default=None),
    ):
        name, version = _parse_name_version(name_version)
        return await _stream_impl(
            name=name,
            req=req,
            version=version,
            authorization=authorization,
        )

    @app.websocket("/api/v1/agents/{name_version}/ws")
    async def api_ws_agent(name_version: str, ws: WebSocket):
        name, version = _parse_name_version(name_version)
        await _ws_handler(ws, fixed_agent_name=name, fixed_version=version)

    # SRS /api/v1 sessions endpoints
    @app.get("/api/v1/sessions/{session_id}")
    async def api_get_session(
        session_id: str,
        authorization: str | None = Header(default=None),
    ):
        _auth(authorization)
        session = session_store.get(session_id)
        if not session:
            return _json_error(1004, f"session_not_found:{session_id}", 404)
        return ApiResponse(data=session.model_dump())

    @app.get("/api/v1/sessions")
    async def api_list_sessions(
        status: SessionStatus | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ):
        _auth(authorization)
        return ApiResponse(data=[s.model_dump() for s in session_store.list_sessions(status)])

    @app.post("/api/v1/sessions/{session_id}/resume")
    async def api_resume_session(
        session_id: str,
        req: ResumeRequest,
        authorization: str | None = Header(default=None),
    ):
        return await _resume_impl(
            session_id=session_id,
            req=req,
            authorization=authorization,
        )

    @app.delete("/api/v1/sessions/{session_id}")
    async def api_delete_session(
        session_id: str,
        authorization: str | None = Header(default=None),
    ):
        return await _terminate_impl(
            session_id=session_id,
            authorization=authorization,
        )

    @app.get("/api/v1/sessions/{session_id}/events")
    async def api_get_session_events(
        session_id: str,
        authorization: str | None = Header(default=None),
    ):
        _auth(authorization)
        return ApiResponse(data=session_store.list_events(session_id))

    @app.get("/api/v1/hitl/suspended")
    async def api_list_suspended_sessions(
        authorization: str | None = Header(default=None),
    ):
        _auth(authorization)
        sessions = session_store.list_sessions(SessionStatus.SUSPENDED)
        return ApiResponse(data=[s.model_dump() for s in sessions])

    @app.get("/api/v1/hitl/{session_id}/form")
    async def api_get_hitl_form(
        session_id: str,
        suspension_id: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ):
        _auth(authorization)
        suspend_event = session_store.get_latest_event(
            session_id,
            event_type="suspend_requested",
            suspension_id=suspension_id,
        )
        if not suspend_event:
            return ApiResponse(data={"mode": "json", "form_schema": {"type": "object", "properties": {"user_input": {"type": "string"}}, "required": ["user_input"]}})
        schema = (suspend_event.get("data") or {}).get("form_schema")
        if not schema:
            return ApiResponse(data={"mode": "json", "form_schema": {"type": "object", "properties": {"user_input": {"type": "string"}}, "required": ["user_input"]}})
        return ApiResponse(data={"mode": "schema", "form_schema": schema})

    @app.post("/api/v1/hitl/{session_id}/submit")
    async def api_submit_hitl_input(
        session_id: str,
        req: ResumeRequest,
        authorization: str | None = Header(default=None),
    ):
        return await _resume_impl(
            session_id=session_id,
            req=req,
            authorization=authorization,
        )

    return app
