from __future__ import annotations

import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable

_NEAREST_DOTENV_CACHE: dict[str, Path | None] = {}
_DOTENV_LOAD_CACHE: dict[str, tuple[int, dict[str, str]]] = {}


def load_env(dotenv_path: str | None = None) -> dict[str, str]:
    path = Path(dotenv_path).expanduser().resolve() if dotenv_path else _find_nearest_dotenv()
    if path is None or not path.exists() or not path.is_file():
        return {}

    stat = path.stat()
    cache_key = str(path)
    cached = _DOTENV_LOAD_CACHE.get(cache_key)
    if cached and cached[0] == stat.st_mtime_ns:
        loaded = cached[1]
        for k, v in loaded.items():
            if k not in os.environ:
                os.environ[k] = v
        return dict(loaded)

    loaded: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        if key not in os.environ:
            os.environ[key] = value
        loaded[key] = value

    _DOTENV_LOAD_CACHE[cache_key] = (stat.st_mtime_ns, dict(loaded))
    return loaded


def _find_nearest_dotenv() -> Path | None:
    cwd = Path.cwd().resolve()
    cached = _NEAREST_DOTENV_CACHE.get(str(cwd))
    if cached is not None:
        return cached

    candidates: list[Path] = []
    for base in [cwd, *cwd.parents]:
        candidates.append(base / ".env")
        candidates.append(base / ".evn")

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.exists() and path.is_file():
            _NEAREST_DOTENV_CACHE[str(cwd)] = path
            return path
    _NEAREST_DOTENV_CACHE[str(cwd)] = None
    return None


def with_env(dotenv_path: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            load_env(dotenv_path)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
