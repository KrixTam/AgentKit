from __future__ import annotations

import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agenthub.config import HubConfig
from agenthub.gateway import create_app


def _manifest(name: str, version: str, entry: str) -> dict:
    return {
        "name": name,
        "version": version,
        "entry": entry,
        "schema": {"type": "object"},
        "runner_config": {"max_turns": 4},
        "tags": ["acceptance"],
    }


def _register(client: TestClient, manifest: dict, aliases: list[str] | None = None) -> None:
    resp = client.post("/api/v1/registry/agents", json={"manifest": manifest, "aliases": aliases or []})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["code"] == 0


def test_acceptance_memory_rest_sse_and_session_replay():
    app = create_app(HubConfig(store_type="memory"))
    client = TestClient(app)

    _register(
        client,
        _manifest("demo-echo", "1.0.0", "tests.fixtures.demo_agents:create_echo_agent"),
        aliases=["stable", "latest"],
    )

    resp = client.get("/api/v1/registry/agents")
    assert resp.status_code == 200
    assert any(x["name"] == "demo-echo" for x in resp.json()["data"])

    invoke = client.post("/api/v1/agents/demo-echo:latest/invoke", json={"input": "hello", "user_id": "u1", "session_id": "s-rest-1"})
    assert invoke.status_code == 200
    data = invoke.json()["data"]
    assert data["run_result"]["success"] is True
    assert data["run_result"]["final_output"] == "echo:hello"

    replay = client.get("/api/v1/sessions/s-rest-1/events")
    assert replay.status_code == 200
    events = replay.json()["data"]
    assert len(events) >= 2
    assert events[0]["seq"] == 1
    assert events[-1]["type"] == "final_output"

    with client.stream("POST", "/api/v1/agents/demo-echo:latest/stream", json={"input": "streaming", "session_id": "sse-1", "user_id": "u1"}) as stream_resp:
        assert stream_resp.status_code == 200
        body = "".join([chunk for chunk in stream_resp.iter_text() if chunk])
    assert "data:" in body
    assert "final_output" in body

    # 会话列表与状态过滤
    listed_all = client.get("/api/v1/sessions")
    assert listed_all.status_code == 200
    assert any(x["session_id"] == "s-rest-1" for x in listed_all.json()["data"])
    listed_completed = client.get("/api/v1/sessions?status=completed")
    assert listed_completed.status_code == 200
    assert any(x["session_id"] == "s-rest-1" for x in listed_completed.json()["data"])


def test_acceptance_ws_hitl_resume_and_hitl_api():
    app = create_app(HubConfig(store_type="memory"))
    client = TestClient(app)

    _register(
        client,
        _manifest("demo-hitl", "1.0.0", "tests.fixtures.demo_agents:create_hitl_agent"),
        aliases=["stable"],
    )

    with client.websocket_connect("/api/v1/agents/demo-hitl:stable/ws") as ws:
        ws.send_text(
            '{"action":"run","input":"do_approval","session_id":"ws-hitl-1","user_id":"u1"}'
        )
        first = ws.receive_json()
        assert first["event"]["type"] == "suspend_requested"
        suspension_id = first["event"]["data"].get("suspension_id")
        assert suspension_id

    suspended = client.get("/api/v1/hitl/suspended")
    assert suspended.status_code == 200
    assert any(x["session_id"] == "ws-hitl-1" for x in suspended.json()["data"])

    form = client.get(f"/api/v1/hitl/ws-hitl-1/form?suspension_id={suspension_id}")
    assert form.status_code == 200
    assert form.json()["data"]["form_schema"]["type"] == "object"

    submit = client.post(
        "/api/v1/hitl/ws-hitl-1/submit",
        json={"user_input": "yes", "suspension_id": suspension_id, "idempotency_key": "k1"},
    )
    assert submit.status_code == 200
    out_events = submit.json()["data"]["events"]
    assert any(e["type"] == "final_output" for e in out_events)

    dup = client.post("/api/v1/hitl/ws-hitl-1/submit", json={"user_input": "yes", "idempotency_key": "k1"})
    assert dup.status_code == 200
    assert dup.json()["data"]["status"] == "duplicate_ignored"


def test_acceptance_sqlite_persistence():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        app1 = create_app(HubConfig(store_type="sqlite", sqlite_path=f.name))
        c1 = TestClient(app1)
        _register(
            c1,
            _manifest("demo-echo", "1.0.1", "tests.fixtures.demo_agents:create_echo_agent"),
            aliases=["latest"],
        )

        app2 = create_app(HubConfig(store_type="sqlite", sqlite_path=f.name))
        c2 = TestClient(app2)
        listed = c2.get("/api/v1/registry/agents").json()["data"]
        assert any(x["name"] == "demo-echo" and x["version"] == "1.0.1" for x in listed)

        alias = c2.post("/api/v1/registry/agents/demo-echo/aliases/stable?version=1.0.1")
        assert alias.status_code == 200
        invoke_alias = c2.post("/api/v1/agents/demo-echo:stable/invoke", json={"input": "ok", "session_id": "alias-s1"})
        assert invoke_alias.status_code == 200
        assert invoke_alias.json()["data"]["run_result"]["success"] is True


def test_acceptance_auth_and_metrics():
    app = create_app(HubConfig(store_type="memory", api_key="secret"))
    client = TestClient(app)
    no_auth = client.get("/api/v1/registry/agents")
    assert no_auth.status_code == 401

    # 旧头不再支持
    old_header = client.get("/api/v1/registry/agents", headers={"x-api-key": "secret"})
    assert old_header.status_code == 401

    ok = client.get("/api/v1/registry/agents", headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "agenthub_requests_total" in metrics.text


def test_model_cosplay_policy_and_hub_override():
    from tests.fixtures.demo_agents import CosplayModelEchoAgent, LockedModelEchoAgent

    with pytest.raises(ValueError):
        LockedModelEchoAgent(name="locked", model="force-override")

    changed = CosplayModelEchoAgent(name="cosplay", model="runtime-model")
    assert changed.model == "runtime-model"

    app = create_app(HubConfig(store_type="memory"))
    client = TestClient(app)
    _register(
        client,
        _manifest("demo-locked-model", "1.0.0", "tests.fixtures.demo_agents:create_locked_model_agent"),
        aliases=["stable"],
    )
    _register(
        client,
        _manifest("demo-cosplay-model", "1.0.0", "tests.fixtures.demo_agents:create_cosplay_model_agent"),
        aliases=["stable"],
    )

    denied = client.post(
        "/api/v1/agents/demo-locked-model:stable/invoke",
        json={"input": "x", "model_cosplay": "forced-model"},
    )
    assert denied.status_code == 400
    assert "未开启 ModelCosplay" in denied.json()["message"]

    ok = client.post(
        "/api/v1/agents/demo-cosplay-model:stable/invoke",
        json={"input": "x", "model_cosplay": "forced-model"},
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["run_result"]["final_output"] == "model:forced-model"


def test_manifest_model_cosplay_default_applied():
    app = create_app(HubConfig(store_type="memory"))
    client = TestClient(app)
    manifest = _manifest("demo-cosplay-default", "1.0.0", "tests.fixtures.demo_agents:create_cosplay_model_agent")
    manifest["model_cosplay"] = "manifest-default-model"
    _register(client, manifest, aliases=["stable"])

    resp = client.post(
        "/api/v1/agents/demo-cosplay-default:stable/invoke",
        json={"input": "x"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["run_result"]["final_output"] == "model:manifest-default-model"
