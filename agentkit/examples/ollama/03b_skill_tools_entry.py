"""
示例 3B：SKILL.md tools.entry 动态工具注册/发现（Ollama 版）

运行前请确保：
  ollama serve
  ollama pull qwen3.5:cloud

运行：
  python examples/ollama/03b_skill_tools_entry.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner, load_skill_from_dir


skill_dir = Path(__file__).resolve().parents[1] / "skills" / "weather-tools-entry"
weather_skill = load_skill_from_dir(skill_dir)

agent = Agent(
    name="skill-tools-entry-agent",
    instructions="你是天气助手。遇到天气问题优先加载并使用 weather-tools-entry Skill。",
    model="ollama/qwen3.5:cloud",
    skills=[weather_skill],
)

queries = [
    "深圳今天适合穿什么？",
    "广州今天需要带伞吗？",
]

for q in queries:
    print(f"\n用户: {q}")
    result = Runner.run_sync(agent, input=q)
    if result.success:
        print(f"助手: {result.final_output}")
    else:
        print(f"❌ 错误: {result.error}")

    for event in result.events:
        if event.type == "tool_result":
            print(f"  🔧 {event.data.get('tool')}: {event.data.get('result')}")
