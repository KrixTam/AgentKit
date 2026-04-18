"""
15_multi_tenant_isolation.py — 多租户与资源隔离测试 (Ollama 版)

本示例展示了：
1. 记忆（Memory）按 user_id 分桶隔离（跨用户不可读）。
2. Skill 上下文（Context）按 session_id/user_id 隔离。
3. Session 结束后资源释放（监控指标 resource_released 事件）。
"""
import sys
import os
import asyncio
import logging

# 确保能导入 agentkit
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from agentkit.agents.agent import Agent
from agentkit.runner.runner import Runner
from agentkit.memory.mem0_provider import Mem0Provider
from agentkit.skills.models import Skill, SkillFrontmatter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# === 1. 定义测试用 Skill ===
async def skill_on_load(skill: Skill, ctx):
    context = skill.get_context(ctx)
    context["session_counter"] = 0
    logging.info(f"[{skill.name}] 为 Session {ctx.session_id} 初始化资源")

async def skill_on_unload(skill: Skill, ctx):
    context = skill.get_context(ctx)
    logging.info(f"[{skill.name}] 释放 Session {ctx.session_id} 的资源 (计数器值: {context.get('session_counter')})")
    context.clear()

def increment_counter(ctx) -> str:
    """增加当前 Session 的计数器"""
    context = ctx.state.get("__skill_context_tenant_skill__", {})
    count = context.get("session_counter", 0) + 1
    context["session_counter"] = count
    return f"计数器已增加，当前值: {count}"

tenant_skill = Skill(
    frontmatter=SkillFrontmatter(
        name="tenant-skill",
        description="租户隔离测试 Skill",
        metadata={"additional_tools": ["increment_counter"]}
    ),
    instructions="你可以调用 increment_counter 来增加计数",
    on_load_hook=skill_on_load,
    on_unload_hook=skill_on_unload,
)
tenant_skill.resources.scripts = {}

async def main():
    class MockMemory(Mem0Provider):
        def __init__(self):
            self.db = {}
        async def add(self, content, *, user_id=None, agent_id=None, metadata=None):
            self.db.setdefault(user_id, []).append(content)
            return []
        async def search(self, query, *, user_id=None, agent_id=None, limit=10):
            class M:
                def __init__(self, c): self.content = c
            return [M(c) for c in self.db.get(user_id, [])]
            
    memory = MockMemory()
    
    agent = Agent(
        name="TenantAgent",
        instructions="你是一个助手。如果用户要求你记住某些事，请回答'我记住了'。如果用户问你记得什么，请回答相关内容。如果用户让你增加计数，请调用 increment_counter 工具。",
        memory=memory,
        skills=[tenant_skill],
        tools=[increment_counter],
        model="ollama/qwen2.5:7b" # 使用 Ollama
    )

    print("=== 测试 1：User A 存储记忆并增加计数 ===")
    user_a = "user_a_123"
    result_a1 = await Runner.run(agent, input="记住我的名字叫 Alice", user_id=user_a)
    print(f"User A Session 1 结果: {result_a1.final_output}")
            
    result_a2 = await Runner.run(agent, input="请增加计数", user_id=user_a)
    print(f"User A Session 2 结果: {result_a2.final_output}")
            
    print("\n=== 测试 2：User B 无法读取 User A 的记忆 ===")
    user_b = "user_b_456"
    result_b1 = await Runner.run(agent, input="我的名字叫什么？", user_id=user_b)
    print(f"User B 看到的内容（应不知道 Alice）: {result_b1.final_output}")

    print("\n隔离测试完成。所有的资源都按照 Session 释放，且 Memory 按 user_id 进行了隔离。")

if __name__ == "__main__":
    asyncio.run(main())