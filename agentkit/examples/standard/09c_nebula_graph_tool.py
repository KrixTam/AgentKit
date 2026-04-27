"""
示例 9C：NebulaGraphTool 最小可执行示例（标准版）

本示例聚焦 NebulaGraphTool 的工具层用法，不依赖真实 Nebula 集群。
通过 Mock ConnectionPool + Mock Formatter，直接调用工具 execute() 完成一次参数化查询演示。
"""
import asyncio
from typing import Any

from pydantic import BaseModel, Field

from agentkit.runner.context import RunContext
from agentkit.tools.nebula_tool import NebulaGraphTool
from agentkit.tools.structured_data import ResultFormatter


class MockSession:
    def execute(self, query: str):
        print(f"[MockSession] execute gql => {query}")
        return "mock_result_set"

    def release(self):
        print("[MockSession] release")


class MockConnectionPool:
    def get_session(self, user: str, password: str):
        print(f"[MockPool] get_session(user={user})")
        return MockSession()


class MockNebulaFormatter(ResultFormatter):
    def format(self, raw_result: Any) -> Any:
        return {
            "summary": "Query succeeded (mock)",
            "data": [
                {"friend_name": "Bob", "relationship": "friend"},
                {"friend_name": "Charlie", "relationship": "colleague"},
            ],
            "raw_type": type(raw_result).__name__,
        }


class PersonQueryArgs(BaseModel):
    name: str = Field(..., description="要查询的用户 ID", pattern=r"^[A-Za-z0-9_]+$")


nebula_tool = NebulaGraphTool(
    name="find_person_friends",
    description="查询某个人在图谱中的朋友关系",
    parameters_schema=PersonQueryArgs,
    query_template=(
        'MATCH (v:person)-[:friend]->(e:person) '
        'WHERE id(v) == "{name}" '
        "RETURN e.name AS friend_name;"
    ),
    space_name="social_graph",
    connection_pool=MockConnectionPool(),
    formatter=MockNebulaFormatter(),
)


async def main():
    ctx = RunContext(input="demo-nebula-tool")
    payload = await nebula_tool.execute(ctx, {"name": "Alice_001"})
    print("\n=== NebulaGraphTool Result ===")
    print(payload)


if __name__ == "__main__":
    asyncio.run(main())

