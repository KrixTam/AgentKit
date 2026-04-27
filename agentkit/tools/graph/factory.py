from __future__ import annotations

import os
from typing import Any

from .litegraph_adapter import LiteGraphAdapter
from .nebula_adapter import NebulaAdapter
from .networkx_adapter import NetworkXAdapter
from .repository import GraphRepository


def create_graph_repository(backend: str, config: dict[str, Any] | None = None) -> GraphRepository:
    cfg = config or {}
    backend_name = (backend or "").strip().lower()
    if backend_name == "networkx":
        adapter = NetworkXAdapter(
            storage_path=cfg.get("storage_path"),
            autosave=cfg.get("autosave", True),
            load_on_start=cfg.get("load_on_start", True),
        )
        return GraphRepository(adapter)
    if backend_name == "litegraph":
        adapter = LiteGraphAdapter(sqlite_path=cfg.get("sqlite_path", ":memory:"))
        return GraphRepository(adapter)
    if backend_name == "nebula":
        space_name = cfg.get("space_name")
        if not space_name:
            raise ValueError("nebula backend requires config.space_name")
        if "connection_pool" not in cfg:
            raise ValueError("nebula backend requires config.connection_pool")
        adapter = NebulaAdapter(
            space_name=space_name,
            connection_pool=cfg["connection_pool"],
            username=cfg.get("username", "root"),
            password=cfg.get("password", "nebula"),
        )
        return GraphRepository(adapter)
    raise ValueError(f"unsupported_graph_backend:{backend_name}")


def create_graph_repository_from_env(
    *,
    env: dict[str, str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> GraphRepository:
    e = env or os.environ
    backend = e.get("AGENTKIT_GRAPH_BACKEND", "networkx")
    cfg: dict[str, Any] = {}
    if backend == "networkx":
        cfg = {
            "storage_path": e.get("AGENTKIT_GRAPH_STORAGE_PATH"),
            "autosave": e.get("AGENTKIT_GRAPH_AUTOSAVE", "true").lower() != "false",
            "load_on_start": e.get("AGENTKIT_GRAPH_LOAD_ON_START", "true").lower() != "false",
        }
    elif backend == "litegraph":
        cfg = {"sqlite_path": e.get("AGENTKIT_GRAPH_SQLITE_PATH", ":memory:")}
    elif backend == "nebula":
        cfg = {
            "space_name": e.get("AGENTKIT_GRAPH_NEBULA_SPACE"),
            "username": e.get("AGENTKIT_GRAPH_NEBULA_USER", "root"),
            "password": e.get("AGENTKIT_GRAPH_NEBULA_PASSWORD", "nebula"),
        }
        if "connection_pool" not in (overrides or {}):
            raise ValueError("nebula backend requires overrides.connection_pool")
    if overrides:
        cfg.update(overrides)
    return create_graph_repository(backend=backend, config=cfg)

