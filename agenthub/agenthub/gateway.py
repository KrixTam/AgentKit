from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse

from agentkit.runner.events import Event
from agentkit.runner.runner import Runner

from .config import HubConfig
from .models import ApiResponse, InvokeRequest, RegisterRequest, ResumeRequest, SessionStatus
from .runtime import (
    HubContextStore,
    Metrics,
    QuotaManager,
    append_event_and_update,
    ensure_session,
    resolve_agent_from_registry,
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

    def _auth(api_key: str | None) -> None:
        if cfg.api_key and api_key != cfg.api_key:
            raise HTTPException(status_code=401, detail="unauthorized")

    def _quota_key(user_id: str | None, tenant_id: str | None) -> str:
        return f"{tenant_id or 'default'}:{user_id or 'anonymous'}"

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "store": cfg.store_type}

    @app.get("/metrics")
    async def metrics_endpoint():
        return PlainTextResponse(metrics.to_prometheus(), media_type="text/plain; version=0.0.4")

    @app.get("/playground")
    async def playground():
        html = """
<!doctype html>
<html><body>
<h3>AgentHub Playground</h3>
<input id='agent' value='demo-agent' />
<input id='input' value='你好' />
<button onclick='run()'>Run</button>
<pre id='out'></pre>
<script>
async function run(){
  const name=document.getElementById('agent').value;
  const input=document.getElementById('input').value;
  const r=await fetch(`/v1/agents/${name}/invoke`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input})});
  document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2);
}
</script>
</body></html>
"""
        return HTMLResponse(html)

    @app.post("/v1/agents/register")
    async def register_agent(req: RegisterRequest, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        try:
            registry_store.register(req.manifest, req.aliases)
            _structured_audit("register_agent", agent=req.manifest.name, version=req.manifest.version)
            return ApiResponse(data={"name": req.manifest.name, "version": req.manifest.version})
        except Exception as e:
            return _json_error(1001, str(e))

    @app.get("/v1/agents")
    async def list_agents(x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        return ApiResponse(data=[m.model_dump(by_alias=True) for m in registry_store.list_all()])

    @app.get("/v1/agents/{name}")
    async def list_agent_versions(name: str, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        return ApiResponse(data=[m.model_dump(by_alias=True) for m in registry_store.list_versions(name)])

    @app.delete("/v1/agents/{name}/{version}")
    async def unregister_agent(name: str, version: str, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        registry_store.unregister(name, version)
        _structured_audit("unregister_agent", agent=name, version=version)
        return ApiResponse(data={"name": name, "version": version, "status": "offline"})

    @app.post("/v1/agents/{name}/aliases/{alias}")
    async def set_alias(name: str, alias: str, version: str = Query(...), x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        try:
            registry_store.set_alias(name, alias, version)
            return ApiResponse(data={"name": name, "alias": alias, "version": version})
        except Exception as e:
            return _json_error(1002, str(e))

    @app.post("/v1/agents/{name}/invoke")
    async def invoke_agent(
        name: str,
        req: InvokeRequest,
        version: str | None = Query(default=None),
        x_api_key: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        _auth(x_api_key)
        quota_key = _quota_key(req.user_id, x_tenant_id)
        start = time.time()
        session_status_for_metrics = SessionStatus.ERROR
        try:
            quota.acquire(quota_key)
            manifest, agent = resolve_agent_from_registry(registry_store, name, version)
            session = ensure_session(
                session_store,
                session_id=req.session_id,
                agent_name=manifest.name,
                agent_version=manifest.version,
                user_id=req.user_id,
                trace_id=req.trace_id or str(uuid.uuid4()),
            )
            result = await Runner.run(
                agent,
                input=req.input,
                context=req.context,
                user_id=req.user_id,
                session_id=session.session_id,
                max_turns=req.max_turns,
            )
            for e in result.events:
                append_event_and_update(session_store, session.session_id, e)
            if result.success:
                session_store.update_status(session.session_id, SessionStatus.COMPLETED)
                session_status_for_metrics = SessionStatus.COMPLETED
            else:
                session_store.update_status(session.session_id, SessionStatus.ERROR, result.error)
                session_status_for_metrics = SessionStatus.ERROR
            _structured_audit("invoke", session_id=session.session_id, agent=name, version=manifest.version, ok=result.success)
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
            session_status_for_metrics = SessionStatus.ERROR
            return _json_error(1003, str(e), status_code=500)
        finally:
            quota.release(quota_key)
            metrics.observe((time.time() - start) * 1000.0, session_status_for_metrics)

    @app.get("/v1/agents/{name}/stream")
    async def invoke_agent_sse(
        name: str,
        input: str = Query(...),
        user_id: str | None = Query(default=None),
        session_id: str | None = Query(default=None),
        trace_id: str | None = Query(default=None),
        version: str | None = Query(default=None),
        x_api_key: str | None = Header(default=None),
    ):
        _auth(x_api_key)
        manifest, agent = resolve_agent_from_registry(registry_store, name, version)
        session = ensure_session(
            session_store,
            session_id=session_id,
            agent_name=manifest.name,
            agent_version=manifest.version,
            user_id=user_id,
            trace_id=trace_id or str(uuid.uuid4()),
        )

        async def gen() -> AsyncGenerator[str, None]:
            try:
                async for e in Runner.run_streamed(agent, input=input, user_id=user_id, session_id=session.session_id):
                    append_event_and_update(session_store, session.session_id, e)
                    payload = {"session_id": session.session_id, "trace_id": session.trace_id, "event": e.to_dict()}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except Exception as ex:
                err = Event(agent=name, type="error", data=str(ex))
                append_event_and_update(session_store, session.session_id, err)
                yield f"data: {json.dumps({'event': err.to_dict()}, ensure_ascii=False)}\n\n"
            finally:
                current = session_store.get(session.session_id)
                if current and current.status == SessionStatus.RUNNING:
                    session_store.update_status(session.session_id, SessionStatus.EXPIRED, "sse_disconnected")

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.websocket("/v1/ws")
    async def ws_gateway(ws: WebSocket):
        await ws.accept()
        active_sessions: set[str] = set()
        try:
            while True:
                text = await ws.receive_text()
                msg = json.loads(text)
                action = msg.get("action")
                api_key = msg.get("api_key")
                _auth(api_key)
                if action == "run":
                    agent_name = msg["agent"]
                    version = msg.get("version")
                    manifest, agent = resolve_agent_from_registry(registry_store, agent_name, version)
                    session = ensure_session(
                        session_store,
                        session_id=msg.get("session_id"),
                        agent_name=manifest.name,
                        agent_version=manifest.version,
                        user_id=msg.get("user_id"),
                        trace_id=msg.get("trace_id") or str(uuid.uuid4()),
                    )
                    async for e in Runner.run_with_checkpoint(
                        agent,
                        input=msg["input"],
                        session_id=session.session_id,
                        context_store=context_store,
                        user_id=msg.get("user_id"),
                    ):
                        append_event_and_update(session_store, session.session_id, e)
                        active_sessions.add(session.session_id)
                        await ws.send_json({"session_id": session.session_id, "trace_id": session.trace_id, "event": e.to_dict()})
                elif action == "resume":
                    session_id = msg["session_id"]
                    session = session_store.get(session_id)
                    if not session:
                        await ws.send_json({"error": f"session_not_found:{session_id}"})
                        continue
                    _, agent = resolve_agent_from_registry(registry_store, session.agent_name, session.agent_version)
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
                    ):
                        append_event_and_update(session_store, session_id, e)
                        active_sessions.add(session_id)
                        await ws.send_json({"session_id": session_id, "event": e.to_dict()})
                else:
                    await ws.send_json({"error": f"unknown_action:{action}"})
        except WebSocketDisconnect:
            for sid in active_sessions:
                session = session_store.get(sid)
                if session and session.status == SessionStatus.RUNNING:
                    session_store.update_status(sid, SessionStatus.EXPIRED, "ws_disconnected")
            return

    @app.get("/v1/sessions")
    async def list_sessions(status: SessionStatus | None = Query(default=None), x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        return ApiResponse(data=[s.model_dump() for s in session_store.list_sessions(status)])

    @app.get("/v1/sessions/{session_id}")
    async def get_session(session_id: str, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        session = session_store.get(session_id)
        if not session:
            return _json_error(1004, f"session_not_found:{session_id}", 404)
        return ApiResponse(data=session.model_dump())

    @app.get("/v1/sessions/{session_id}/events")
    async def replay_events(session_id: str, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        return ApiResponse(data=session_store.list_events(session_id))

    @app.post("/v1/sessions/{session_id}/resume")
    async def resume_session(session_id: str, req: ResumeRequest, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        session = session_store.get(session_id)
        if not session:
            return _json_error(1004, f"session_not_found:{session_id}", 404)
        if req.idempotency_key and session.metadata.get("last_resume_key") == req.idempotency_key:
            return ApiResponse(data={"session_id": session_id, "status": "duplicate_ignored"})
        if req.idempotency_key:
            session.metadata["last_resume_key"] = req.idempotency_key
        _, agent = resolve_agent_from_registry(registry_store, session.agent_name, session.agent_version)
        events: list[dict[str, Any]] = []
        async for e in Runner.resume(
            agent,
            session_id=session_id,
            user_input=req.user_input,
            context_store=context_store,
        ):
            append_event_and_update(session_store, session_id, e)
            events.append(e.to_dict())
        return ApiResponse(data={"session_id": session_id, "events": events})

    @app.post("/v1/sessions/{session_id}/terminate")
    async def terminate_session(session_id: str, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        session_store.terminate(session_id)
        _structured_audit("terminate_session", session_id=session_id)
        return ApiResponse(data={"session_id": session_id, "status": "terminated"})

    @app.get("/v1/hitl/suspended")
    async def list_suspended_sessions(x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        sessions = session_store.list_sessions(SessionStatus.SUSPENDED)
        return ApiResponse(data=[s.model_dump() for s in sessions])

    @app.get("/v1/hitl/{session_id}/form")
    async def get_hitl_form(session_id: str, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        events = session_store.list_events(session_id)
        suspend_event = next((e for e in reversed(events) if e.get("type") == "suspend_requested"), None)
        if not suspend_event:
            return ApiResponse(data={"mode": "json", "form_schema": {"type": "object", "properties": {"user_input": {"type": "string"}}, "required": ["user_input"]}})
        schema = (suspend_event.get("data") or {}).get("form_schema")
        if not schema:
            return ApiResponse(data={"mode": "json", "form_schema": {"type": "object", "properties": {"user_input": {"type": "string"}}, "required": ["user_input"]}})
        return ApiResponse(data={"mode": "schema", "form_schema": schema})

    @app.post("/v1/hitl/{session_id}/submit")
    async def submit_hitl_input(session_id: str, req: ResumeRequest, x_api_key: str | None = Header(default=None)):
        _auth(x_api_key)
        session = session_store.get(session_id)
        if not session:
            return _json_error(1004, f"session_not_found:{session_id}", 404)
        if req.idempotency_key and session.metadata.get("last_resume_key") == req.idempotency_key:
            return ApiResponse(data={"session_id": session_id, "status": "duplicate_ignored"})
        if req.idempotency_key:
            session.metadata["last_resume_key"] = req.idempotency_key
        _, agent = resolve_agent_from_registry(registry_store, session.agent_name, session.agent_version)
        events: list[dict[str, Any]] = []
        async for e in Runner.resume(
            agent,
            session_id=session_id,
            user_input=req.user_input,
            context_store=context_store,
        ):
            append_event_and_update(session_store, session_id, e)
            events.append(e.to_dict())
        return ApiResponse(data={"session_id": session_id, "events": events})

    return app
