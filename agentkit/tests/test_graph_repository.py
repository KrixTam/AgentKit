from __future__ import annotations

import asyncio
import os
import tempfile

from agentkit.runner.context import RunContext
from agentkit.tools.graph.factory import create_graph_repository
from agentkit.tools.graph.models import EdgeSpec, NodeSpec, QuerySpec
from agentkit.tools.graph.tool import GraphQueryTool


def test_litegraph_repository_query_flow():
    async def _case() -> None:
        repo = create_graph_repository("litegraph")
        await repo.upsert_node(NodeSpec(node_id="alice", label="person", properties={"city": "SZ"}))
        await repo.upsert_node(NodeSpec(node_id="bob", label="person", properties={"city": "BJ"}))
        await repo.upsert_edge(EdgeSpec(source_id="alice", target_id="bob", edge_type="friend"))

        neighbors = await repo.query(QuerySpec(operation="neighbors", node_id="alice", direction="out"))
        assert neighbors.backend == "litegraph"
        assert any(row.get("node_id") == "bob" for row in neighbors.rows)

        path = await repo.query(QuerySpec(operation="shortest_path", source_id="alice", target_id="bob"))
        assert path.summary == "path_found"
        assert path.rows[0]["path"] == ["alice", "bob"]

        await repo.close()

    asyncio.run(_case())


def test_networkx_repository_persistence_if_available():
    async def _case() -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage_path = os.path.join(tmp_dir, "graph.json")
            repo = create_graph_repository(
                "networkx",
                {"storage_path": storage_path, "autosave": True, "load_on_start": True},
            )
            await repo.upsert_node(NodeSpec(node_id="n1", properties={"city": "SZ"}))
            await repo.upsert_node(NodeSpec(node_id="n2", properties={"city": "BJ"}))
            await repo.upsert_edge(EdgeSpec(source_id="n1", target_id="n2", edge_type="link"))
            await repo.close()

            repo2 = create_graph_repository(
                "networkx",
                {"storage_path": storage_path, "autosave": True, "load_on_start": True},
            )
            result = await repo2.query(QuerySpec(operation="neighbors", node_id="n1", direction="out"))
            await repo2.close()
            assert any(row.get("node_id") == "n2" for row in result.rows)

    try:
        asyncio.run(_case())
    except RuntimeError as e:
        if "networkx is not installed" not in str(e):
            raise


def test_graph_query_tool_with_repository():
    async def _case() -> None:
        repo = create_graph_repository("litegraph")
        await repo.upsert_node(NodeSpec(node_id="alice"))
        await repo.upsert_node(NodeSpec(node_id="bob"))
        await repo.upsert_edge(EdgeSpec(source_id="alice", target_id="bob", edge_type="friend"))

        tool = GraphQueryTool(repository=repo)
        payload = await tool.execute(
            RunContext(input="graph query"),
            {
                "operation": "neighbors",
                "node_id": "alice",
                "direction": "out",
            },
        )
        await repo.close()

        assert payload["backend"] == "litegraph"
        assert any(row.get("node_id") == "bob" for row in payload["rows"])

    asyncio.run(_case())

