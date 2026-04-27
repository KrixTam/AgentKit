from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class NodeSpec(BaseModel):
    node_id: str
    label: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class EdgeSpec(BaseModel):
    source_id: str
    target_id: str
    edge_type: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    directed: bool = True


class QuerySpec(BaseModel):
    operation: Literal["neighbors", "shortest_path", "find_nodes", "edges"]
    node_id: str | None = None
    source_id: str | None = None
    target_id: str | None = None
    edge_type: str | None = None
    direction: Literal["out", "in", "both"] = "both"
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 50
    max_hops: int = 8


class GraphResult(BaseModel):
    backend: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

