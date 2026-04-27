from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import EdgeSpec, GraphResult, NodeSpec, QuerySpec


class GraphAdapter(ABC):
    @property
    @abstractmethod
    def backend(self) -> str:
        ...

    @abstractmethod
    async def upsert_node(self, node: NodeSpec) -> None:
        ...

    @abstractmethod
    async def upsert_edge(self, edge: EdgeSpec) -> None:
        ...

    @abstractmethod
    async def query(self, spec: QuerySpec) -> GraphResult:
        ...

    @abstractmethod
    async def healthcheck(self) -> dict[str, Any]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

