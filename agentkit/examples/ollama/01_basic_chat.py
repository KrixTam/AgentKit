"""
示例 1：最简 Agent — 纯对话（Ollama 本地版）

运行前请确保 Ollama 已启动：
  ollama serve
  ollama pull qwen3.5:cloud

运行：
  python examples/ollama/01_basic_chat.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner

# 创建最简 Agent —— 使用本地 Ollama 模型
agent = Agent(
    name="assistant",
    instructions="你是一个有帮助的中文助手。回答尽量简洁。",
    model="ollama/qwen3.5:cloud",      # 本地 Ollama 模型，无需 API Key
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
