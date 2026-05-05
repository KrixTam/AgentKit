"""标准示例统一模型配置。"""

from __future__ import annotations

import os
from pathlib import Path


def _read_value_from_local_env_file(key: str) -> str | None:
    """从当前目录向上查找 .env/.evn，读取形如 KEY=VALUE 的配置。"""
    candidates: list[Path] = []
    cwd = Path.cwd().resolve()
    candidates.append(cwd / ".env")
    candidates.append(cwd / ".evn")

    here = Path(__file__).resolve()
    for base in [here.parent, *here.parents]:
        candidates.append(base / ".env")
        candidates.append(base / ".evn")

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if not path.exists() or not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() != key:
                    continue
                value = v.strip().strip("'").strip('"')
                return value or None
        except Exception:
            continue
    return None


def resolve_model(default_model: str) -> str:
    """
    标准示例模型解析规则：
    1) 优先读取环境变量 AGENTKIT_STANDARD_MODEL；
    2) 其次读取本地 .env/.evn 中的 AGENTKIT_STANDARD_MODEL；
    3) 都没有时使用各样例原有默认模型。
    """
    value = (os.getenv("AGENTKIT_STANDARD_MODEL") or "").strip()
    if not value:
        value = (_read_value_from_local_env_file("AGENTKIT_STANDARD_MODEL") or "").strip()
    return value or default_model
