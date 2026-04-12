"""
示例 1：最简 Agent — 纯对话

运行前请设置环境变量：
  export OPENAI_API_KEY="sk-..."

运行：
  python examples/standard/01_basic_chat.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner

# 创建最简 Agent —— 只需 3 个参数
agent = Agent(
    name="assistant",
    instructions="你是一个有帮助的中文助手。回答尽量简洁。",
    model="gpt-4o",
)

# 同步运行
result = Runner.run_sync(agent, input="什么是量子计算？请用一句话解释。")

if result.success:
    print(f"✅ 回复: {result.final_output}")
else:
    print(f"❌ 错误: {result.error}")

# 查看事件流
print("\n📋 事件流:")
for event in result.events:
    print(f"  [{event.type}] {str(event.data)[:80]}")
