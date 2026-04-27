from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..structured_data import StructuredDataTool
from ...runner.context import RunContext
from .models import QuerySpec
from .repository import GraphRepository


class GraphQueryArgs(BaseModel):
    operation: str = Field(description="查询操作：neighbors/shortest_path/find_nodes/edges")
    node_id: str | None = None
    source_id: str | None = None
    target_id: str | None = None
    edge_type: str | None = None
    direction: str = "both"
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 50
    max_hops: int = 8


class GraphQueryTool(StructuredDataTool):
    """统一图查询 Tool，底层可切换 networkx/litegraph/nebula。"""

    def __init__(
        self,
        *,
        repository: GraphRepository,
        name: str = "graph_query",
        description: str = "在图数据源中执行参数化查询（支持多后端切换）",
    ):
        super().__init__(
            name=name,
            description=description,
            parameters_schema=GraphQueryArgs,
        )
        self._repository = repository

    async def execute_query(self, ctx: RunContext, args: BaseModel) -> Any:
        spec = QuerySpec.model_validate(args.model_dump())
        result = await self._repository.query(spec)
        return result.model_dump()

