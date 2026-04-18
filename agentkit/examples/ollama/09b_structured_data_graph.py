import asyncio
import logging
from typing import Any
from pydantic import BaseModel, Field
from agentkit import Agent, Runner

from agentkit.tools.structured_data import ResultFormatter
from agentkit.tools.nebula_tool import NebulaGraphTool, NEBULA_AVAILABLE

logging.basicConfig(level=logging.INFO)

# ==========================================
# Mock Nebula 客户端对象（无需安装真实 Nebula 也可运行此示例）
# ==========================================

class MockSession:
    def execute(self, query: str):
        logging.info(f"[Nebula Session] 执行 GQL 查询: {query}")
        return "mock_result_set"
    def release(self):
        logging.info("[Nebula Session] 释放连接")

class MockConnectionPool:
    def get_session(self, user, password):
        logging.info(f"[Nebula Pool] 获取会话，用户: {user}")
        return MockSession()

class MockResultFormatter(ResultFormatter):
    """由于没有真实的 ResultSet，我们在这里 Mock 返回的结果"""
    def format(self, raw_result: Any) -> Any:
        # 在真实场景中，你会使用 NebulaResultFormatter 解析 raw_result (即 ResultSet 对象)
        return {
            "summary": "Query succeeded, found 2 records.",
            "data": [
                {"friend_name": "Bob", "relationship": "friend", "since": "2020"},
                {"friend_name": "Charlie", "relationship": "colleague", "since": "2022"}
            ]
        }

# ==========================================
# AgentKit NebulaGraphTool 配置
# ==========================================

# 1. 定义查询参数 Schema
class PersonQueryArgs(BaseModel):
    name: str = Field(..., description="要查找的人的名字", pattern=r"^[A-Za-z0-9_]+$")

# 2. 实例化参数化 Nebula 工具
nebula_tool = NebulaGraphTool(
    name="find_person_friends",
    description="在知识图谱中查找某个人的朋友",
    parameters_schema=PersonQueryArgs,
    # 内部将安全地通过 args.model_dump() 将校验过的参数注入，避免注入攻击
    query_template='MATCH (v:person)-[:friend]->(e:person) WHERE id(v) == "{name}" RETURN e.name AS friend_name;',
    space_name="social_graph",
    connection_pool=MockConnectionPool(), # 注入 Mock 连接池
    formatter=MockResultFormatter(),      # 注入 Mock 格式化器
)

async def main():
    agent = Agent(
        name="GraphAssistant",
        instructions="你是一个图数据库查询助手，请帮我查询并用自然语言总结结果。",
        model="ollama/qwen3.5:cloud", # Ollama 版
        tools=[nebula_tool],
    )
    
    print("\n--- Agent 正在运行 ---\n")
    # 让 Agent 去查图数据库
    result = await Runner.run(agent, input="请帮我在图谱里找一下 Alice 的朋友。")
    
    print(f"\n🤖 最终回复:\n{result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
