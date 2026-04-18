import asyncio
import sqlite3
from pydantic import BaseModel, Field
from agentkit import Agent, Runner
from agentkit.tools.sqlite_tool import SQLiteTool

# 1. 准备 Mock 的 SQLite 数据库
DB_PATH = "/tmp/agentkit_demo.db"

def init_mock_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT, age INTEGER)")
    mock_data = [
        ("Alice", "Admin", 30),
        ("Bob", "User", 25),
        ("Charlie", "User", 35),
    ]
    cursor.executemany("INSERT INTO users (name, role, age) VALUES (?, ?, ?)", mock_data)
    conn.commit()
    conn.close()
    print(f"✅ 初始化 SQLite Mock 数据库成功 ({DB_PATH})，已插入 3 条记录。")

# 2. 定义严格的参数 Schema，让 LLM 只需要输出参数
class UserRoleQueryArgs(BaseModel):
    role: str = Field(..., description="要查询的用户角色名称，例如 'Admin' 或 'User'")

# 3. 实例化参数化 SQLite 工具
# 使用 :role 占位符。底层 SQLiteTool 会使用 cursor.execute(sql, dict) 绑定参数，彻底杜绝 SQL 注入。
sqlite_tool = SQLiteTool(
    name="query_users_by_role",
    description="根据角色查询用户信息",
    parameters_schema=UserRoleQueryArgs,
    query_template="SELECT name, age FROM users WHERE role = :role;",
    db_path=DB_PATH,
)

async def main():
    init_mock_db()
    
    agent = Agent(
        name="DBAssistant",
        instructions="你是一个数据库查询助手，请帮用户查询数据库。如果查询成功，请用中文自然地回复查询结果。",
        model="gpt-4o", # 标准版使用 GPT-4o
        tools=[sqlite_tool],
    )
    
    print("\n--- Agent 正在运行 ---\n")
    # 让 Agent 去查角色为 User 的人
    result = await Runner.run(agent, input="请帮我查一下，数据库里角色为 User 的人有哪些？")
    
    print(f"🤖 最终回复:\n{result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
