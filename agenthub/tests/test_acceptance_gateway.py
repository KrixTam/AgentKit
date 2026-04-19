from __future__ import annotations

import os
import sys
import tempfile

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
    resp = client.post("/v1/agents/register", json={"manifest": manifest, "aliases": aliases or []})
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

    resp = client.get("/v1/agents")
    assert resp.status_code == 200
    assert any(x["name"] == "demo-echo" for x in resp.json()["data"])

    invoke = client.post("/v1/agents/demo-echo/invoke", json={"input": "hello", "user_id": "u1", "session_id": "s-rest-1"})
    assert invoke.status_code == 200
    data = invoke.json()["data"]
    assert data["run_result"]["success"] is True
    assert data["run_result"]["final_output"] == "echo:hello"

    replay = client.get("/v1/sessions/s-rest-1/events")
    assert replay.status_code == 200
    events = replay.json()["data"]
    assert len(events) >= 2
    assert events[0]["seq"] == 1
    assert events[-1]["type"] == "final_output"

    with client.stream("GET", "/v1/agents/demo-echo/stream?input=streaming&session_id=sse-1&user_id=u1") as stream_resp:
        assert stream_resp.status_code == 200
        body = "".join([chunk for chunk in stream_resp.iter_text() if chunk])
    assert "data:" in body
    assert "final_output" in body


def test_acceptance_ws_hitl_resume_and_hitl_api():
    app = create_app(HubConfig(store_type="memory"))
    client = TestClient(app)

    _register(
        client,
        _manifest("demo-hitl", "1.0.0", "tests.fixtures.demo_agents:create_hitl_agent"),
        aliases=["stable"],
    )

    with client.websocket_connect("/v1/ws") as ws:
        ws.send_text(
            '{"action":"run","agent":"demo-hitl","version":"stable","input":"do_approval","session_id":"ws-hitl-1","user_id":"u1"}'
        )
        first = ws.receive_json()
        assert first["event"]["type"] == "suspend_requested"

    suspended = client.get("/v1/hitl/suspended")
    assert suspended.status_code == 200
    assert any(x["session_id"] == "ws-hitl-1" for x in suspended.json()["data"])

    form = client.get("/v1/hitl/ws-hitl-1/form")
    assert form.status_code == 200
    assert form.json()["data"]["form_schema"]["type"] == "object"

    submit = client.post("/v1/hitl/ws-hitl-1/submit", json={"user_input": "yes", "idempotency_key": "k1"})
    assert submit.status_code == 200
    out_events = submit.json()["data"]["events"]
    assert any(e["type"] == "final_output" for e in out_events)

    dup = client.post("/v1/hitl/ws-hitl-1/submit", json={"user_input": "yes", "idempotency_key": "k1"})
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
        listed = c2.get("/v1/agents").json()["data"]
        assert any(x["name"] == "demo-echo" and x["version"] == "1.0.1" for x in listed)


def test_acceptance_auth_and_metrics():
    app = create_app(HubConfig(store_type="memory", api_key="secret"))
    client = TestClient(app)
    no_auth = client.get("/v1/agents")
    assert no_auth.status_code == 401

    ok = client.get("/v1/agents", headers={"x-api-key": "secret"})
    assert ok.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "agenthub_requests_total" in metrics.text
