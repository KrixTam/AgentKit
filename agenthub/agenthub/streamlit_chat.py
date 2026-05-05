from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import streamlit as st


def _request(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    token: str | None = None,
) -> tuple[int, dict[str, Any]]:
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
        return 503, {"code": 503, "message": f"gateway_unreachable:{e.reason}"}


def _load_registry(server: str, token: str | None) -> tuple[dict[str, Any], str | None]:
    status, payload = _request("GET", f"{server}/api/v1/registry/agents", token=token)
    if status >= 400:
        return {}, payload.get("message") or f"http_{status}"
    records = payload.get("data") or []
    grouped: dict[str, list[str]] = {}
    for item in records:
        name = str(item.get("name", "")).strip()
        version = str(item.get("version", "")).strip()
        if not name or not version:
            continue
        grouped.setdefault(name, [])
        if version not in grouped[name]:
            grouped[name].append(version)
    for versions in grouped.values():
        versions.sort()
    return grouped, None


def main() -> None:
    st.set_page_config(page_title="AgentHub Chat", page_icon="💬", layout="wide")
    st.title("AgentHub Chat")
    st.caption("基于已注册 Agent 的对话页面（通过 AgentHub /invoke 网关）")

    default_server = os.getenv("AGENTHUB_CHAT_SERVER", "http://127.0.0.1:8008")
    default_token = os.getenv("AGENTHUB_CHAT_TOKEN", "")
    default_name = os.getenv("AGENTHUB_CHAT_AGENT_NAME", "")
    default_version = os.getenv("AGENTHUB_CHAT_AGENT_VERSION", "latest")
    default_user_id = os.getenv("AGENTHUB_CHAT_USER_ID", "")
    default_model_cosplay = os.getenv("AGENTHUB_CHAT_MODEL_COSPLAY", "")
    default_max_turns = int(os.getenv("AGENTHUB_CHAT_MAX_TURNS", "10"))

    with st.sidebar:
        st.header("连接配置")
        server = st.text_input("Server", value=default_server).rstrip("/")
        token = st.text_input("Token (Bearer)", value=default_token, type="password").strip()
        user_id = st.text_input("user_id", value=default_user_id).strip()
        model_cosplay = st.text_input("model_cosplay (可选)", value=default_model_cosplay).strip()
        max_turns = st.number_input("max_turns", min_value=1, max_value=100, value=default_max_turns, step=1)
        refresh = st.button("刷新已注册 Agent")

    if "registry_cache" not in st.session_state:
        st.session_state.registry_cache = {}
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = ""
    if "agent_name" not in st.session_state:
        st.session_state.agent_name = default_name
    if "agent_version" not in st.session_state:
        st.session_state.agent_version = default_version

    if refresh or not st.session_state.registry_cache:
        grouped, err = _load_registry(server, token or None)
        if err:
            st.error(f"加载已注册 Agent 失败: {err}")
        else:
            st.session_state.registry_cache = grouped

    grouped = st.session_state.registry_cache
    if not grouped:
        st.warning("当前没有可用的已注册 Agent，请先在 AgentHub 注册后再使用聊天。")
        return

    names = sorted(grouped.keys())
    selected_name = st.selectbox(
        "选择 Agent",
        names,
        index=names.index(st.session_state.agent_name) if st.session_state.agent_name in names else 0,
    )
    versions = grouped.get(selected_name, [])
    version_options = ["latest"] + versions
    selected_version = st.selectbox(
        "版本或别名",
        version_options,
        index=version_options.index(st.session_state.agent_version) if st.session_state.agent_version in version_options else 0,
    )

    st.session_state.agent_name = selected_name
    st.session_state.agent_version = selected_version

    if st.button("清空会话"):
        st.session_state.messages = []
        st.session_state.session_id = ""
        st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("输入消息并回车")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    payload: dict[str, Any] = {
        "input": user_input,
        "max_turns": int(max_turns),
    }
    if user_id:
        payload["user_id"] = user_id
    if st.session_state.session_id:
        payload["session_id"] = st.session_state.session_id
    if model_cosplay:
        payload["model_cosplay"] = model_cosplay

    name_version = f"{selected_name}:{selected_version}"
    status, resp = _request(
        "POST",
        f"{server}/api/v1/agents/{urllib.parse.quote(name_version)}/invoke",
        payload,
        token=token or None,
    )

    if status >= 400:
        message = resp.get("message") or f"http_{status}"
        with st.chat_message("assistant"):
            st.error(message)
        st.session_state.messages.append({"role": "assistant", "content": f"Error: {message}"})
        return

    data = resp.get("data") or {}
    run_result = data.get("run_result") or {}
    answer = run_result.get("final_output")
    if answer is None:
        answer = "(empty response)"
    st.session_state.session_id = data.get("session_id") or st.session_state.session_id

    with st.chat_message("assistant"):
        st.markdown(str(answer))
    st.session_state.messages.append({"role": "assistant", "content": str(answer)})

    if st.session_state.session_id:
        st.caption(f"session_id: {st.session_state.session_id}")


if __name__ == "__main__":
    main()
