import asyncio
import logging
from agentkit import Agent, Runner, Skill, SkillFrontmatter

logging.basicConfig(level=logging.INFO)

# 1. 定义资源初始化和释放的钩子
async def init_db_pool(skill: Skill):
    logging.info(f"[{skill.name}] on_load_hook: 正在建立外部数据库连接池...")
    # 将生成的资源绑定到 Skill 的 context 字典中，确保同生命周期安全管理
    skill.context["db_pool"] = "MockConnectionPool(size=10)"

async def close_db_pool(skill: Skill):
    logging.info(f"[{skill.name}] on_unload_hook: 正在释放外部数据库连接池...")
    pool = skill.context.get("db_pool")
    if pool:
        logging.info(f"[{skill.name}] 已成功关闭连接池: {pool}")
        skill.context.clear()

# 2. 定义带生命周期的 Skill
db_skill = Skill(
    frontmatter=SkillFrontmatter(
        name="database-skill",
        description="提供数据库查询能力，并在加载和卸载时自动管理连接池",
    ),
    instructions="你可以安全地使用关联的数据库连接池进行查询。",
    on_load_hook=init_db_pool,
    on_unload_hook=close_db_pool,
)

async def main():
    agent = Agent(
        name="assistant",
        instructions="你是一个助手，请简短回答即可。",
        model="gpt-4o",
        skills=[db_skill],
    )
    
    print("开始运行 Agent，观察控制台输出的生命周期日志：\n")
    # 运行前后会自动触发 on_load 和 on_unload
    result = await Runner.run(agent, input="你好！")
    print(f"\n✅ 最终输出: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
