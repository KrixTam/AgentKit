from __future__ import annotations

from typing import Any

from .models import EdgeSpec, GraphResult, NodeSpec, QuerySpec
from .protocols import GraphAdapter

try:
    from nebula3.data.ResultSet import ResultSet

    NEBULA_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    NEBULA_AVAILABLE = False
    ResultSet = Any


class NebulaAdapter(GraphAdapter):
    def __init__(
        self,
        *,
        space_name: str,
        connection_pool: Any,
        username: str = "root",
        password: str = "nebula",
    ):
        self._space_name = space_name
        self._connection_pool = connection_pool
        self._username = username
        self._password = password

    @property
    def backend(self) -> str:
        return "nebula"

    async def upsert_node(self, node: NodeSpec) -> None:
        if not node.label:
            raise ValueError("Nebula upsert_node requires node.label as tag")
        props = self._kv_props(node.properties)
        stmt = f'INSERT VERTEX {node.label}({",".join(node.properties.keys())}) VALUES "{self._q(node.node_id)}":({props});'
        self._execute(stmt)

    async def upsert_edge(self, edge: EdgeSpec) -> None:
        if not edge.edge_type:
            raise ValueError("Nebula upsert_edge requires edge.edge_type")
        props = self._kv_props(edge.properties)
        stmt = (
            f'INSERT EDGE {edge.edge_type}({",".join(edge.properties.keys())}) VALUES '
            f'"{self._q(edge.source_id)}"->"{self._q(edge.target_id)}":({props});'
        )
        self._execute(stmt)

    async def query(self, spec: QuerySpec) -> GraphResult:
        gql = self._build_query(spec)
        result = self._execute(gql)
        return self._resultset_to_graph_result(result)

    async def healthcheck(self) -> dict[str, Any]:
        try:
            result = self._execute("SHOW SPACES;")
            ok = getattr(result, "is_succeeded", lambda: True)()
            return {"ok": bool(ok), "backend": self.backend, "space": self._space_name}
        except Exception as e:
            return {"ok": False, "backend": self.backend, "space": self._space_name, "error": str(e)}

    async def close(self) -> None:
        return None

    def _execute(self, gql: str) -> Any:
        if not NEBULA_AVAILABLE:
            raise RuntimeError("nebula3-python is not installed")
        pool = self._connection_pool() if callable(self._connection_pool) else self._connection_pool
        if pool is None:
            raise RuntimeError("Nebula connection_pool is not initialized")
        session = pool.get_session(self._username, self._password)
        try:
            session.execute(f"USE {self._space_name};")
            return session.execute(gql)
        finally:
            session.release()

    def _build_query(self, spec: QuerySpec) -> str:
        if spec.operation == "neighbors":
            if not spec.node_id:
                raise ValueError("neighbors query requires node_id")
            limit = max(1, min(spec.limit, 5000))
            node = self._q(spec.node_id)
            if spec.direction == "in":
                return f'MATCH (n)-[e]->(v) WHERE id(v)=="{node}" RETURN id(n) AS node_id, type(e) AS edge_type LIMIT {limit};'
            if spec.direction == "out":
                return f'MATCH (v)-[e]->(n) WHERE id(v)=="{node}" RETURN id(n) AS node_id, type(e) AS edge_type LIMIT {limit};'
            return (
                f'MATCH (v)-[e]->(n) WHERE id(v)=="{node}" RETURN id(n) AS node_id, "out" AS direction, type(e) AS edge_type '
                f"UNION ALL "
                f'MATCH (n)-[e]->(v) WHERE id(v)=="{node}" RETURN id(n) AS node_id, "in" AS direction, type(e) AS edge_type '
                f"LIMIT {limit};"
            )

        if spec.operation == "shortest_path":
            if not spec.source_id or not spec.target_id:
                raise ValueError("shortest_path query requires source_id and target_id")
            max_hops = max(1, min(spec.max_hops, 64))
            return (
                f'FIND SHORTEST PATH FROM "{self._q(spec.source_id)}" TO "{self._q(spec.target_id)}" '
                f"OVER * UPTO {max_hops} STEPS;"
            )

        if spec.operation == "find_nodes":
            limit = max(1, min(spec.limit, 5000))
            return f"MATCH (v) RETURN id(v) AS node_id LIMIT {limit};"

        if spec.operation == "edges":
            limit = max(1, min(spec.limit, 5000))
            return f"MATCH ()-[e]->() RETURN src(e) AS source_id, dst(e) AS target_id, type(e) AS edge_type LIMIT {limit};"

        raise ValueError(f"unsupported_operation:{spec.operation}")

    def _resultset_to_graph_result(self, result: Any) -> GraphResult:
        if isinstance(result, ResultSet):
            if not result.is_succeeded():
                return GraphResult(
                    backend=self.backend,
                    summary="nebula_query_failed",
                    meta={"code": result.error_code(), "message": result.error_msg()},
                )
            keys = list(result.keys())
            rows: list[dict[str, Any]] = []
            for row in result.rows():
                parsed: dict[str, Any] = {}
                for idx, val in enumerate(row.values):
                    parsed[keys[idx]] = str(val.get_value())
                rows.append(parsed)
            return GraphResult(backend=self.backend, rows=rows, summary=f"rows:{len(rows)}")
        return GraphResult(backend=self.backend, rows=[{"raw": str(result)}], summary="non_resultset")

    @staticmethod
    def _q(v: str) -> str:
        return v.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _kv_props(props: dict[str, Any]) -> str:
        if not props:
            return ""
        parts: list[str] = []
        for value in props.values():
            if isinstance(value, bool):
                parts.append("true" if value else "false")
            elif isinstance(value, (int, float)):
                parts.append(str(value))
            else:
                escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
                parts.append(f'"{escaped}"')
        return ",".join(parts)

