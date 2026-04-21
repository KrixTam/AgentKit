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
            return _json_error(1001, str(e))

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
            manifest, agent = _resolve_agent_instance_observed(name, version, obs)
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
        manifest, agent = _resolve_agent_instance_observed(name, version, obs)
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
                async for e in Runner.run_streamed(
                    agent,
                    input=req.input,
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
                    manifest, agent = _resolve_agent_instance_observed(agent_name, version, obs)
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
