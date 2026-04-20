from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import uvicorn

from .config import HubConfig
from .gateway import create_app
from .manifest import load_manifest


def _request(
    method: str,
    url: str,
    payload: dict | None = None,
    *,
    token: str | None = None,
) -> tuple[int, dict]:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
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
    parser.add_argument("--token", default=os.getenv("AGENTHUB_TOKEN"), help="Bearer token")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_register = sub.add_parser("register")
    p_register.add_argument("manifest")
    p_register.add_argument("--alias", action="append", default=[])

    sub.add_parser("list")

    p_unregister = sub.add_parser("unregister")
    p_unregister.add_argument("name_version", help="格式: <name>:<version>")

    p_info = sub.add_parser("info")
    p_info.add_argument("name")
    p_info.add_argument("--version")

    p_run = sub.add_parser("run")
    p_run.add_argument("name")
    p_run.add_argument("--version")
    p_run.add_argument("--input", required=True)
    p_run.add_argument("--model-cosplay")
    p_run.add_argument("--user-id")
    p_run.add_argument("--session-id")

    p_trace = sub.add_parser("trace")
    p_trace.add_argument("session_id")

    p_session = sub.add_parser("session")
    p_session_sub = p_session.add_subparsers(dest="session_cmd", required=True)
    p_session_list = p_session_sub.add_parser("list")
    p_session_list.add_argument("--status", choices=["running", "suspended", "completed", "error", "expired", "terminated"])
    p_session_get = p_session_sub.add_parser("get")
    p_session_get.add_argument("session_id")
    p_session_resume = p_session_sub.add_parser("resume")
    p_session_resume.add_argument("session_id")
    p_session_resume.add_argument("--input", required=True, dest="resume_input")
    p_session_term = p_session_sub.add_parser("terminate")
    p_session_term.add_argument("session_id")

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
            f"{server}/api/v1/registry/agents",
            {"manifest": manifest.model_dump(by_alias=True), "aliases": args.alias},
            token=args.token,
        )
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "list":
        status, data = _request("GET", f"{server}/api/v1/registry/agents", token=args.token)
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "unregister":
        status, data = _request(
            "DELETE",
            f"{server}/api/v1/registry/agents/{urllib.parse.quote(args.name_version)}",
            token=args.token,
        )
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "info":
        status, data = _request(
            "GET",
            f"{server}/api/v1/registry/agents/{urllib.parse.quote(args.name)}",
            token=args.token,
        )
        if status < 400 and args.version:
            payload = data.get("data", [])
            data["data"] = [x for x in payload if x.get("version") == args.version]
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "run":
        payload = {
            "input": args.input,
            "model_cosplay": args.model_cosplay,
            "user_id": args.user_id,
            "session_id": args.session_id,
        }
        name_version = f"{args.name}:{args.version}" if args.version else args.name
        status, data = _request(
            "POST",
            f"{server}/api/v1/agents/{urllib.parse.quote(name_version)}/invoke",
            payload,
            token=args.token,
        )
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "trace":
        status, data = _request(
            "GET",
            f"{server}/api/v1/sessions/{args.session_id}/events",
            token=args.token,
        )
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)

    if args.cmd == "session":
        if args.session_cmd == "list":
            query = f"?status={urllib.parse.quote(args.status)}" if args.status else ""
            status, data = _request("GET", f"{server}/api/v1/sessions{query}", token=args.token)
        elif args.session_cmd == "get":
            status, data = _request(
                "GET",
                f"{server}/api/v1/sessions/{args.session_id}",
                token=args.token,
            )
        elif args.session_cmd == "resume":
            status, data = _request(
                "POST",
                f"{server}/api/v1/sessions/{args.session_id}/resume",
                {"user_input": args.resume_input},
                token=args.token,
            )
        elif args.session_cmd == "terminate":
            status, data = _request(
                "DELETE",
                f"{server}/api/v1/sessions/{args.session_id}",
                token=args.token,
            )
        else:
            status, data = 2, {"code": 2, "message": "unknown session sub-command"}
        _print_output(data, args.json)
        sys.exit(0 if status < 400 else 2)


if __name__ == "__main__":
    main()
