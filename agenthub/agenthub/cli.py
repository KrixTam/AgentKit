from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import uvicorn
import yaml

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
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        return 503, {
            "code": 503,
            "message": f"gateway_unreachable:{reason}",
            "hint": "请先启动 AgentHub 网关，例如：agenthub serve --store sqlite --sqlite-path .agenthub/agenthub.db",
        }


def _print_output(data: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def _safe_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _derive_name_from_entry(entry: str) -> str:
    fallback = "generated-agent"
    try:
        module_name, attr_name = entry.split(":", 1)
    except ValueError:
        return fallback
    leaf = _safe_str(attr_name, fallback).replace("_", "-").lower()
    if leaf.startswith("create-"):
        leaf = leaf[len("create-") :]
    if leaf.endswith("-agent"):
        return leaf
    if leaf == "agent":
        if module_name.endswith(".py") or "/" in module_name or module_name.startswith("."):
            module_leaf = Path(module_name).stem.replace("_", "-").lower()
        else:
            module_leaf = module_name.split(".")[-1].replace("_", "-").lower()
        return module_leaf or fallback
    return leaf or fallback


def _is_file_entry_target(target: str) -> bool:
    return target.endswith(".py") or "/" in target or target.startswith(".")


def _load_module_from_file(file_target: str):
    file_path = Path(file_target).expanduser()
    if not file_path.is_absolute():
        file_path = (Path.cwd() / file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"entry 文件不存在: {file_path}")
    module_name = f"_agenthub_manifest_{file_path.stem}_{abs(hash(str(file_path)))}"
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"无法从文件加载模块: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_entry_object(entry: str) -> object:
    module_name, attr_name = entry.split(":", 1)
    module_name = module_name.strip()
    attr_name = attr_name.strip()
    if not module_name or not attr_name:
        raise ValueError("entry 格式必须为 module:attr 或 path.py:attr")

    if _is_file_entry_target(module_name):
        module = _load_module_from_file(module_name)
    else:
        module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    return value() if callable(value) else value


def _build_manifest_from_entry(
    entry: str,
    *,
    name: str | None = None,
    version: str = "1.0.0",
    description: str | None = None,
    max_turns: int = 10,
) -> dict:
    obj = _load_entry_object(entry)
    resolved_name = _safe_str(name, _safe_str(getattr(obj, "name", None), _derive_name_from_entry(entry)))
    resolved_description = _safe_str(
        description,
        _safe_str(getattr(obj, "description", None), f"Generated manifest for {resolved_name}"),
    )
    return {
        "name": resolved_name,
        "version": version,
        "description": resolved_description,
        "entry": entry,
        "skills": [],
        "input_schema": {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
            },
            "required": ["input"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "final_output": {"type": "string"},
            },
        },
        "requires_human_input": False,
        "runner_config": {
            "max_turns": max_turns,
            "default_hub_port": 8008,
        },
        "tags": ["generated"],
    }


def _manifest_generate_error_payload(entry: str, exc: Exception) -> dict:
    payload = {
        "code": 2,
        "message": f"manifest_generate_failed:{exc}",
    }
    if isinstance(exc, ValueError):
        payload["hint"] = "entry 格式应为 `module:attr` 或 `path.py:attr`，例如 `agenthub.demo_agent:create_agent`。"
        return payload
    if isinstance(exc, FileNotFoundError):
        payload["hint"] = f"未找到入口文件，请检查路径是否存在（当前工作目录：{Path.cwd()}）。"
        return payload
    if isinstance(exc, ModuleNotFoundError):
        payload["hint"] = "无法导入模块，请检查模块名、虚拟环境依赖与当前执行目录。"
        return payload
    if isinstance(exc, AttributeError):
        payload["hint"] = f"入口 `{entry}` 的 attr 不存在，请确认模块/文件中定义了该符号。"
        return payload
    if isinstance(exc, TypeError):
        payload["hint"] = "入口若为工厂函数，应支持无参调用；或让 entry 指向已创建的 Agent 实例。"
        return payload
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(prog="agenthub")
    parser.add_argument("--server", default="http://127.0.0.1:8008")
    parser.add_argument("--token", default=os.getenv("AGENTHUB_TOKEN"), help="Bearer token")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_register = sub.add_parser("register")
    p_register.add_argument("manifest")
    p_register.add_argument("--alias", action="append", default=[])

    p_manifest = sub.add_parser("manifest")
    p_manifest_sub = p_manifest.add_subparsers(dest="manifest_cmd", required=True)
    p_manifest_gen = p_manifest_sub.add_parser("generate")
    p_manifest_gen.add_argument("--entry", required=True, help="Agent 入口，格式 module:attr 或 path.py:attr")
    p_manifest_gen.add_argument("--name", help="Manifest 中的 agent 名称（不传则自动推断）")
    p_manifest_gen.add_argument("--version", default="1.0.0", help="Manifest 版本（语义化版本）")
    p_manifest_gen.add_argument("--description", help="Manifest 描述（不传则自动推断）")
    p_manifest_gen.add_argument("--max-turns", type=int, default=10, help="runner_config.max_turns")
    p_manifest_gen.add_argument("--output", default="agent.yaml", help="输出文件路径")
    p_manifest_gen.add_argument("--force", action="store_true", help="覆盖已存在的输出文件")

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
    p_serve.add_argument("--log-file", default=None, help="日志文件路径（默认 .agenthub/agenthub.log）")
    p_serve.add_argument("--log-level", default=None, help="日志级别（DEBUG/INFO/WARNING/ERROR）")

    p_chat = sub.add_parser("chat")
    p_chat.add_argument("--server", dest="chat_server", help="AgentHub 服务地址（覆盖全局 --server）")
    p_chat.add_argument("--token", dest="chat_token", help="Bearer token（覆盖全局 --token）")
    p_chat.add_argument("--name", help="默认选中的 Agent 名称")
    p_chat.add_argument("--version", help="默认选中的版本或别名（默认 latest）")
    p_chat.add_argument("--user-id", help="默认 user_id")
    p_chat.add_argument("--model-cosplay", help="默认 model_cosplay")
    p_chat.add_argument("--max-turns", type=int, default=10, help="默认 max_turns")
    p_chat.add_argument("--port", type=int, default=8501, help="Streamlit 页面端口")

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
        if args.log_file:
            cfg.log_file = args.log_file
        if args.log_level:
            cfg.log_level = args.log_level
        app = create_app(cfg)
        uvicorn.run(app, host=cfg.host, port=cfg.port)
        return

    if args.cmd == "chat":
        chat_server = (args.chat_server or server).rstrip("/")
        chat_token = args.chat_token if args.chat_token is not None else args.token
        env = os.environ.copy()
        env["AGENTHUB_CHAT_SERVER"] = chat_server
        if chat_token:
            env["AGENTHUB_CHAT_TOKEN"] = chat_token
        if args.name:
            env["AGENTHUB_CHAT_AGENT_NAME"] = args.name
        if args.version:
            env["AGENTHUB_CHAT_AGENT_VERSION"] = args.version
        if args.user_id:
            env["AGENTHUB_CHAT_USER_ID"] = args.user_id
        if args.model_cosplay:
            env["AGENTHUB_CHAT_MODEL_COSPLAY"] = args.model_cosplay
        env["AGENTHUB_CHAT_MAX_TURNS"] = str(args.max_turns)

        app_path = os.path.join(os.path.dirname(__file__), "streamlit_chat.py")
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            app_path,
            "--server.port",
            str(args.port),
        ]
        try:
            completed = subprocess.run(cmd, env=env, check=False)
        except FileNotFoundError:
            print(
                json.dumps(
                    {
                        "code": 2,
                        "message": "streamlit_not_found: 请先安装 `pip install \"ni.agenthub[chat]\"` 或 `pip install streamlit`",
                    },
                    ensure_ascii=False,
                )
            )
            sys.exit(2)
        except KeyboardInterrupt:
            # 用户主动 Ctrl+C 结束 Streamlit 会话时，避免打印回溯噪音
            sys.exit(130)
        sys.exit(completed.returncode)

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

    if args.cmd == "manifest":
        if args.manifest_cmd == "generate":
            output_path = Path(args.output).expanduser().resolve()
            if output_path.exists() and not args.force:
                _print_output(
                    {
                        "code": 2,
                        "message": f"output_exists:{output_path}",
                        "hint": "使用 --force 覆盖已有文件",
                    },
                    args.json,
                )
                sys.exit(2)
            try:
                manifest = _build_manifest_from_entry(
                    args.entry,
                    name=args.name,
                    version=args.version,
                    description=args.description,
                    max_turns=args.max_turns,
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)
            except Exception as e:
                _print_output(_manifest_generate_error_payload(args.entry, e), args.json)
                sys.exit(2)
            _print_output(
                {
                    "code": 0,
                    "message": "ok",
                    "data": {"output": str(output_path), "manifest": manifest},
                },
                args.json,
            )
            sys.exit(0)

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
