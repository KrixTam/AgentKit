from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import uvicorn

from .config import HubConfig
from .gateway import create_app
from .manifest import load_manifest


def _request(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"code": e.code, "message": body}


def _print_output(data: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="agenthub")
    parser.add_argument("--server", default="http://127.0.0.1:8008")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_register = sub.add_parser("register")
    p_register.add_argument("manifest")
    p_register.add_argument("--alias", action="append", default=[])

    sub.add_parser("list")

    p_info = sub.add_parser("info")
    p_info.add_argument("name")
    p_info.add_argument("--version")

    p_run = sub.add_parser("run")
    p_run.add_argument("name")
    p_run.add_argument("--version")
    p_run.add_argument("--input", required=True)
    p_run.add_argument("--user-id")
    p_run.add_argument("--session-id")

    p_trace = sub.add_parser("trace")
    p_trace.add_argument("session_id")

    p_session = sub.add_parser("session")
    p_session.add_argument("session_id")
    p_session.add_argument("--resume")
    p_session.add_argument("--terminate", action="store_true")

    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.add_argument("--store", choices=["memory", "sqlite"], default=None)
    p_serve.add_argument("--sqlite-path", default=None)

    args = parser.parse_args()
    server = args.server.rstrip("/")

    if args.cmd == "serve":
        cfg = HubConfig.from_env()
        if args.host:
            cfg.host = args.host
        if args.port:
            cfg.port = args.port
        if args.store:
            cfg.store_type = args.store
        if args.sqlite_path:
            cfg.sqlite_path = args.sqlite_path
        app = create_app(cfg)
        uvicorn.run(app, host=cfg.host, port=cfg.port)
        return

    if args.cmd == "register":
        manifest = load_manifest(args.manifest)
        status, data = _request(
            "POST",
            f"{server}/v1/agents/register",
            {"manifest": manifest.model_dump(by_alias=True), "aliases": args.alias},
        )
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "list":
        status, data = _request("GET", f"{server}/v1/agents")
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "info":
        if args.version:
            status, data = _request("GET", f"{server}/v1/agents/{args.name}?version={urllib.parse.quote(args.version)}")
        else:
            status, data = _request("GET", f"{server}/v1/agents/{args.name}")
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "run":
        payload = {
            "input": args.input,
            "user_id": args.user_id,
            "session_id": args.session_id,
        }
        version_query = f"?version={urllib.parse.quote(args.version)}" if args.version else ""
        status, data = _request("POST", f"{server}/v1/agents/{args.name}/invoke{version_query}", payload)
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "trace":
        status, data = _request("GET", f"{server}/v1/sessions/{args.session_id}/events")
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "session":
        if args.terminate:
            status, data = _request("POST", f"{server}/v1/sessions/{args.session_id}/terminate")
        elif args.resume is not None:
            status, data = _request("POST", f"{server}/v1/sessions/{args.session_id}/resume", {"user_input": args.resume})
        else:
            status, data = _request("GET", f"{server}/v1/sessions/{args.session_id}")
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)


if __name__ == "__main__":
    main()
