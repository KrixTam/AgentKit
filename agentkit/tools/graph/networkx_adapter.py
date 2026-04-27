from __future__ import annotations

import json
import os
from typing import Any

from .models import EdgeSpec, GraphResult, NodeSpec, QuerySpec
from .protocols import GraphAdapter

try:
    import networkx as nx
    from networkx.readwrite import json_graph

    NETWORKX_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    NETWORKX_AVAILABLE = False
    nx = None
    json_graph = None


class NetworkXAdapter(GraphAdapter):
    def __init__(
        self,
        *,
        storage_path: str | None = None,
        autosave: bool = True,
        load_on_start: bool = True,
    ):
        if not NETWORKX_AVAILABLE:
            raise RuntimeError("networkx is not installed, please install it first")

        self._storage_path = storage_path
        self._autosave = autosave
        self._graph = nx.MultiDiGraph()
        if storage_path and load_on_start and os.path.exists(storage_path):
            self._load()

    @property
    def backend(self) -> str:
        return "networkx"

    async def upsert_node(self, node: NodeSpec) -> None:
        attrs = dict(node.properties)
        if node.label is not None:
            attrs["label"] = node.label
        self._graph.add_node(node.node_id, **attrs)
        self._maybe_save()

    async def upsert_edge(self, edge: EdgeSpec) -> None:
        attrs = dict(edge.properties)
        if edge.edge_type is not None:
            attrs["edge_type"] = edge.edge_type
        self._graph.add_edge(edge.source_id, edge.target_id, **attrs)
        if not edge.directed:
            self._graph.add_edge(edge.target_id, edge.source_id, **attrs)
        self._maybe_save()

    async def query(self, spec: QuerySpec) -> GraphResult:
        op = spec.operation
        if op == "neighbors":
            return self._query_neighbors(spec)
        if op == "shortest_path":
            return self._query_shortest_path(spec)
        if op == "find_nodes":
            return self._query_find_nodes(spec)
        if op == "edges":
            return self._query_edges(spec)
        return GraphResult(backend=self.backend, summary=f"unsupported_operation:{op}")

    async def healthcheck(self) -> dict[str, Any]:
        return {
            "ok": True,
            "backend": self.backend,
            "nodes": self._graph.number_of_nodes(),
            "edges": self._graph.number_of_edges(),
            "storage_path": self._storage_path,
        }

    async def close(self) -> None:
        self._maybe_save(force=True)

    def _query_neighbors(self, spec: QuerySpec) -> GraphResult:
        if not spec.node_id or spec.node_id not in self._graph:
            return GraphResult(backend=self.backend, summary="node_not_found")

        rows: list[dict[str, Any]] = []
        node_id = spec.node_id
        if spec.direction in ("out", "both"):
            for _, target, data in self._graph.out_edges(node_id, data=True):
                if spec.edge_type and data.get("edge_type") != spec.edge_type:
                    continue
                rows.append({"node_id": target, "direction": "out", "edge": data})

        if spec.direction in ("in", "both"):
            for source, _, data in self._graph.in_edges(node_id, data=True):
                if spec.edge_type and data.get("edge_type") != spec.edge_type:
                    continue
                rows.append({"node_id": source, "direction": "in", "edge": data})

        return GraphResult(
            backend=self.backend,
            rows=rows[: spec.limit],
            summary=f"neighbors:{len(rows[: spec.limit])}",
        )

    def _query_shortest_path(self, spec: QuerySpec) -> GraphResult:
        if not spec.source_id or not spec.target_id:
            return GraphResult(backend=self.backend, summary="source_or_target_missing")
        try:
            path = nx.shortest_path(self._graph.to_undirected(), spec.source_id, spec.target_id)
        except Exception:
            return GraphResult(backend=self.backend, summary="path_not_found")
        return GraphResult(
            backend=self.backend,
            rows=[{"path": path, "hops": max(len(path) - 1, 0)}],
            summary="path_found",
        )

    def _query_find_nodes(self, spec: QuerySpec) -> GraphResult:
        rows: list[dict[str, Any]] = []
        for node_id, attrs in self._graph.nodes(data=True):
            if not self._matches_filters(attrs, spec.filters):
                continue
            rows.append({"node_id": node_id, "properties": dict(attrs)})
        return GraphResult(
            backend=self.backend,
            rows=rows[: spec.limit],
            summary=f"nodes:{len(rows[: spec.limit])}",
        )

    def _query_edges(self, spec: QuerySpec) -> GraphResult:
        rows: list[dict[str, Any]] = []
        for source, target, attrs in self._graph.edges(data=True):
            if spec.edge_type and attrs.get("edge_type") != spec.edge_type:
                continue
            rows.append({"source_id": source, "target_id": target, "properties": dict(attrs)})
        return GraphResult(
            backend=self.backend,
            rows=rows[: spec.limit],
            summary=f"edges:{len(rows[: spec.limit])}",
        )

    @staticmethod
    def _matches_filters(attrs: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            if attrs.get(key) != expected:
                return False
        return True

    def _maybe_save(self, *, force: bool = False) -> None:
        if not self._storage_path:
            return
        if not self._autosave and not force:
            return
        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        payload = json_graph.node_link_data(self._graph, edges="edges")
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

    def _load(self) -> None:
        with open(self._storage_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self._graph = json_graph.node_link_graph(payload, directed=True, multigraph=True, edges="edges")
