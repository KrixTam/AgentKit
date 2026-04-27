from __future__ import annotations

from .models import EdgeSpec, GraphResult, NodeSpec, QuerySpec
from .protocols import GraphAdapter


class GraphRepository:
    """统一图数据访问入口，屏蔽底层图库/图库服务差异。"""

    def __init__(self, adapter: GraphAdapter):
        self._adapter = adapter

    @property
    def backend(self) -> str:
        return self._adapter.backend

    async def upsert_node(self, node: NodeSpec) -> None:
        await self._adapter.upsert_node(node)

    async def upsert_edge(self, edge: EdgeSpec) -> None:
        await self._adapter.upsert_edge(edge)

    async def query(self, spec: QuerySpec) -> GraphResult:
        return await self._adapter.query(spec)

    async def healthcheck(self) -> dict:
        return await self._adapter.healthcheck()

    async def close(self) -> None:
        await self._adapter.close()

