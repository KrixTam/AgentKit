from __future__ import annotations

import json
import sqlite3
from collections import deque
from typing import Any

from .models import EdgeSpec, GraphResult, NodeSpec, QuerySpec
from .protocols import GraphAdapter


class LiteGraphAdapter(GraphAdapter):
    """基于 SQLite 的轻量图存储适配器（开发/测试场景）。"""

    def __init__(self, *, sqlite_path: str = ":memory:"):
        self._sqlite_path = sqlite_path
        self._conn = sqlite3.connect(sqlite_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    @property
    def backend(self) -> str:
        return "litegraph"

    async def upsert_node(self, node: NodeSpec) -> None:
        props = dict(node.properties)
        if node.label is not None:
            props["label"] = node.label
        self._conn.execute(
            """
            INSERT INTO graph_nodes(node_id, label, properties_json)
            VALUES(?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
              label=excluded.label,
              properties_json=excluded.properties_json
            """,
            (node.node_id, node.label, json.dumps(props, ensure_ascii=False)),
        )
        self._conn.commit()

    async def upsert_edge(self, edge: EdgeSpec) -> None:
        self._conn.execute(
            """
            INSERT INTO graph_edges(source_id, target_id, edge_type, directed, properties_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                edge.source_id,
                edge.target_id,
                edge.edge_type,
                1 if edge.directed else 0,
                json.dumps(edge.properties, ensure_ascii=False),
            ),
        )
        if not edge.directed:
            self._conn.execute(
                """
                INSERT INTO graph_edges(source_id, target_id, edge_type, directed, properties_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    edge.target_id,
                    edge.source_id,
                    edge.edge_type,
                    1,
                    json.dumps(edge.properties, ensure_ascii=False),
                ),
            )
        self._conn.commit()

    async def query(self, spec: QuerySpec) -> GraphResult:
        if spec.operation == "neighbors":
            return self._query_neighbors(spec)
        if spec.operation == "shortest_path":
            return self._query_shortest_path(spec)
        if spec.operation == "find_nodes":
            return self._query_find_nodes(spec)
        if spec.operation == "edges":
            return self._query_edges(spec)
        return GraphResult(backend=self.backend, summary=f"unsupported_operation:{spec.operation}")

    async def healthcheck(self) -> dict[str, Any]:
        nodes = self._conn.execute("SELECT COUNT(1) AS c FROM graph_nodes").fetchone()["c"]
        edges = self._conn.execute("SELECT COUNT(1) AS c FROM graph_edges").fetchone()["c"]
        return {"ok": True, "backend": self.backend, "nodes": nodes, "edges": edges, "sqlite_path": self._sqlite_path}

    async def close(self) -> None:
        self._conn.close()

    def _query_neighbors(self, spec: QuerySpec) -> GraphResult:
        if not spec.node_id:
            return GraphResult(backend=self.backend, summary="node_id_missing")

        rows: list[dict[str, Any]] = []
        params: list[Any] = [spec.node_id]
        condition = "source_id = ?"
        if spec.edge_type:
            condition += " AND edge_type = ?"
            params.append(spec.edge_type)
        if spec.direction in ("out", "both"):
            for row in self._conn.execute(
                f"SELECT target_id, edge_type, properties_json FROM graph_edges WHERE {condition} LIMIT ?",
                [*params, spec.limit],
            ).fetchall():
                rows.append(
                    {
                        "node_id": row["target_id"],
                        "direction": "out",
                        "edge_type": row["edge_type"],
                        "edge": json.loads(row["properties_json"] or "{}"),
                    }
                )

        if spec.direction in ("in", "both"):
            params_in: list[Any] = [spec.node_id]
            cond_in = "target_id = ?"
            if spec.edge_type:
                cond_in += " AND edge_type = ?"
                params_in.append(spec.edge_type)
            for row in self._conn.execute(
                f"SELECT source_id, edge_type, properties_json FROM graph_edges WHERE {cond_in} LIMIT ?",
                [*params_in, spec.limit],
            ).fetchall():
                rows.append(
                    {
                        "node_id": row["source_id"],
                        "direction": "in",
                        "edge_type": row["edge_type"],
                        "edge": json.loads(row["properties_json"] or "{}"),
                    }
                )
        return GraphResult(backend=self.backend, rows=rows[: spec.limit], summary=f"neighbors:{len(rows[: spec.limit])}")

    def _query_shortest_path(self, spec: QuerySpec) -> GraphResult:
        if not spec.source_id or not spec.target_id:
            return GraphResult(backend=self.backend, summary="source_or_target_missing")
        if spec.source_id == spec.target_id:
            return GraphResult(backend=self.backend, rows=[{"path": [spec.source_id], "hops": 0}], summary="path_found")

        graph: dict[str, set[str]] = {}
        for row in self._conn.execute("SELECT source_id, target_id FROM graph_edges").fetchall():
            graph.setdefault(row["source_id"], set()).add(row["target_id"])

        visited = {spec.source_id}
        queue = deque([(spec.source_id, [spec.source_id])])
        while queue:
            node, path = queue.popleft()
            if len(path) - 1 >= spec.max_hops:
                continue
            for nxt in graph.get(node, set()):
                if nxt in visited:
                    continue
                new_path = path + [nxt]
                if nxt == spec.target_id:
                    return GraphResult(
                        backend=self.backend,
                        rows=[{"path": new_path, "hops": len(new_path) - 1}],
                        summary="path_found",
                    )
                visited.add(nxt)
                queue.append((nxt, new_path))
        return GraphResult(backend=self.backend, summary="path_not_found")

    def _query_find_nodes(self, spec: QuerySpec) -> GraphResult:
        rows: list[dict[str, Any]] = []
        for row in self._conn.execute("SELECT node_id, properties_json FROM graph_nodes LIMIT ?", (spec.limit * 5,)).fetchall():
            props = json.loads(row["properties_json"] or "{}")
            ok = True
            for key, expected in spec.filters.items():
                if props.get(key) != expected:
                    ok = False
                    break
            if ok:
                rows.append({"node_id": row["node_id"], "properties": props})
            if len(rows) >= spec.limit:
                break
        return GraphResult(backend=self.backend, rows=rows, summary=f"nodes:{len(rows)}")

    def _query_edges(self, spec: QuerySpec) -> GraphResult:
        rows: list[dict[str, Any]] = []
        if spec.edge_type:
            cursor = self._conn.execute(
                "SELECT source_id, target_id, edge_type, properties_json FROM graph_edges WHERE edge_type = ? LIMIT ?",
                (spec.edge_type, spec.limit),
            )
        else:
            cursor = self._conn.execute(
                "SELECT source_id, target_id, edge_type, properties_json FROM graph_edges LIMIT ?",
                (spec.limit,),
            )
        for row in cursor.fetchall():
            rows.append(
                {
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "edge_type": row["edge_type"],
                    "properties": json.loads(row["properties_json"] or "{}"),
                }
            )
        return GraphResult(backend=self.backend, rows=rows, summary=f"edges:{len(rows)}")

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_nodes(
                node_id TEXT PRIMARY KEY,
                label TEXT,
                properties_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_edges(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                edge_type TEXT,
                directed INTEGER NOT NULL DEFAULT 1,
                properties_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_src ON graph_edges(source_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_dst ON graph_edges(target_id)")
        self._conn.commit()

