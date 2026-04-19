from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import AgentManifest


def load_manifest(path: str | Path) -> AgentManifest:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    try:
        return AgentManifest.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Manifest 校验失败: {e}") from e
