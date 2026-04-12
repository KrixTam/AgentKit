"""
示例 2：带工具的 Agent — Function Calling（Ollama 本地版）

演示 @function_tool 装饰器 + 本地 Ollama 的 Function Calling 能力。

运行前请确保 Ollama 已启动：
  ollama serve
  ollama pull qwen3.5:cloud

运行：
  python examples/ollama/02_tool_calling.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner, function_tool


# ===== 定义工具 =====

@function_tool
def add(a: int, b: int) -> str:
    """两个数字相加"""
    return str(a + b)

@function_tool
def multiply(a: int, b: int) -> str:
    """两个数字相乘"""
    return str(a * b)

@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    weather_data = {
        "北京": "晴，25°C",
        "上海": "多云，22°C",
        "深圳": "阵雨，28°C",
    }
    return weather_data.get(city, f"{city}：暂无数据")


# ===== 创建 Agent =====

agent = Agent(
    name="smart-assistant",
    instructions="你是一个全能助手。可以做数学计算和查天气。根据用户需求选择合适的工具。回答简洁。",
    model="ollama/qwen3.5:cloud",
    tools=[add, multiply, get_weather],
)


# ===== 运行测试 =====

queries = [
    "请计算 15 + 27 的结果",
    "3 乘以 7 等于多少？",
    "北京今天天气如何？",
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
            print(f"  🔧 工具调用: {event.data}")
