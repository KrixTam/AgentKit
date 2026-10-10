from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import AgentManifest


def _is_file_entry_target(target: str) -> bool:
    return target.endswith(".py") or "/" in target or "\\" in target or target.startswith(".")


def _normalize_entry(entry: str, manifest_path: Path) -> str:
    module_name, attr_name = entry.split(":", 1)
    module_name = module_name.strip()
    attr_name = attr_name.strip()
    if not module_name or not attr_name:
        return entry

    if not _is_file_entry_target(module_name):
        return entry

    file_path = Path(module_name).expanduser()
    if not file_path.is_absolute():
        file_path = (manifest_path.parent / file_path).resolve()
    return f"{file_path}:{attr_name}"


def load_manifest(path: str | Path) -> AgentManifest:
    manifest_path = Path(path).expanduser().resolve()
    with open(manifest_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    try:
        manifest = AgentManifest.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Manifest 校验失败: {e}") from e
    return manifest.model_copy(update={"entry": _normalize_entry(manifest.entry, manifest_path)})
