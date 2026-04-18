"""
examples/test_ollama.py — 使用本地 Ollama (qwen3.5:cloud) 测试 AgentKit 框架

测试内容：
  1. 基础对话（纯文本）
  2. 工具调用（function calling）
  3. Skill 使用（三级加载）
  4. 安全护栏
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agentkit.agents.agent import Agent
from agentkit.runner.runner import Runner
from agentkit.tools.function_tool import function_tool
from agentkit.skills.models import Skill, SkillFrontmatter
from agentkit.safety.guardrails import input_guardrail, GuardrailResult
from agentkit.llm.registry import LLMRegistry

# 使用的模型
MODEL = "ollama/qwen3.5:cloud"


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


# ============================================================
# 测试 1：基础对话
# ============================================================

async def test_basic_chat():
    separator("测试 1：基础对话")

    agent = Agent(
        name="basic-assistant",
        instructions="你是一个简洁的中文助手。回答尽量简短。",
        model=MODEL,
    )

    result = await Runner.run(agent, input="请用一句话解释什么是人工智能。")
    if result.success:
        print(f"✅ 回复: {result.final_output}")
    else:
        print(f"❌ 错误: {result.error}")

    # 打印事件流
    for event in result.events:
        print(f"   [{event.type}] {str(event.data)[:80]}...")


# ============================================================
# 测试 2：工具调用（Function Calling）
# ============================================================

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


async def test_tool_calling():
    separator("测试 2：工具调用")

    agent = Agent(
        name="math-assistant",
        instructions="你是一个数学助手。需要计算时，请使用提供的工具。回答简洁。",
        model=MODEL,
        tools=[add, multiply],
    )

    result = await Runner.run(agent, input="请计算 15 + 27 的结果")
    if result.success:
        print(f"✅ 回复: {result.final_output}")
    else:
        print(f"❌ 错误: {result.error}")

    # 打印事件
    for event in result.events:
        if event.type == "tool_result":
            print(f"   🔧 工具调用: {event.data}")
        elif event.type == "final_output":
            print(f"   📝 最终输出: {event.data}")


async def test_weather_tool():
    separator("测试 2b：天气查询工具")

    agent = Agent(
        name="weather-assistant",
        instructions="你是一个天气助手。用户问天气时，使用 get_weather 工具查询。回答简洁。",
        model=MODEL,
        tools=[get_weather],
    )

    result = await Runner.run(agent, input="北京今天天气怎么样？")
    if result.success:
        print(f"✅ 回复: {result.final_output}")
    else:
        print(f"❌ 错误: {result.error}")

    for event in result.events:
        if event.type == "tool_result":
            print(f"   🔧 工具调用: {event.data}")


# ============================================================
# 测试 3：Skill 使用
# ============================================================

async def test_skill():
    separator("测试 3：Skill 使用")

    # 定义一个天气分析 Skill
    weather_skill = Skill(
        frontmatter=SkillFrontmatter(
            name="weather-analysis",
            description="天气分析技能，能够查询天气并给出穿衣建议",
        ),
        instructions="""## 天气分析步骤

1. 使用 get_weather 工具查询用户指定城市的天气
2. 根据天气情况给出穿衣建议：
   - 温度 > 30°C：建议穿短袖
   - 温度 20-30°C：建议穿薄外套
   - 温度 < 20°C：建议穿厚外套
3. 用简洁的中文回复用户""",
    )

    agent = Agent(
        name="skill-agent",
        instructions="你是一个智能助手，可以使用 Skill 来完成复杂任务。",
        model=MODEL,
        skills=[weather_skill],
        tools=[get_weather],
    )

    result = await Runner.run(agent, input="深圳今天适合穿什么衣服？")
    if result.success:
        print(f"✅ 回复: {result.final_output}")
    else:
        print(f"❌ 错误: {result.error}")

    for event in result.events:
        if event.type in ("tool_result", "final_output"):
            print(f"   [{event.type}] {str(event.data)[:100]}")


# ============================================================
# 测试 4：安全护栏
# ============================================================

@input_guardrail
async def block_sensitive_words(ctx):
    sensitive = ["密码", "身份证", "银行卡号"]
    for word in sensitive:
        if word in ctx.input:
            return GuardrailResult(triggered=True, reason=f"包含敏感词: {word}")
    return GuardrailResult(triggered=False)


async def test_guardrail():
    separator("测试 4：安全护栏")

    agent = Agent(
        name="safe-agent",
        instructions="你是一个安全的助手。",
        model=MODEL,
        input_guardrails=[block_sensitive_words],
    )

    # 测试 4a：敏感请求应被拦截
    result = await Runner.run(agent, input="请告诉我你的密码")
    if result.error:
        print(f"✅ 敏感请求被正确拦截: {result.error}")
    else:
        print(f"❌ 敏感请求未被拦截！输出: {result.final_output}")

    # 测试 4b：正常请求应通过
    result = await Runner.run(agent, input="你好，今天天气怎么样？")
    if result.success:
        print(f"✅ 正常请求通过: {result.final_output}")
    else:
        print(f"❌ 正常请求被误拦截: {result.error}")


# ============================================================
# 测试 5：多工具 Agent
# ============================================================

async def test_multi_tool():
    separator("测试 5：多工具组合")

    agent = Agent(
        name="multi-tool-agent",
        instructions="你是一个全能助手。可以做数学计算，也可以查天气。根据用户需求选择合适的工具。回答简洁。",
        model=MODEL,
        tools=[add, multiply, get_weather],
    )

    queries = [
        "3乘以7等于多少？",
        "上海今天天气如何？",
        "100加200是多少？",
    ]

    for q in queries:
        print(f"  用户: {q}")
        result = await Runner.run(agent, input=q)
        if result.success:
            print(f"  助手: {result.final_output}")
        else:
            print(f"  ❌ 错误: {result.error}")

        # 展示工具调用
        for event in result.events:
            if event.type == "tool_result":
                print(f"    🔧 {event.data}")
        print()


# ============================================================
# 主入口
# ============================================================

async def main():
    print("🚀 AgentKit 框架测试 — 使用 Ollama qwen3.5:cloud")
    print(f"   模型标识: {MODEL}")

    # 验证 Ollama 连接
    try:
        llm = LLMRegistry.create(MODEL)
        print(f"   适配器: {type(llm).__name__}")
        print(f"   实际模型: {llm.config.model}")
        print(f"   API 端点: {llm.config.api_base or llm._base_url}")
    except Exception as e:
        print(f"❌ 无法创建 LLM 实例: {e}")
        return

    # 依次运行测试
    await test_basic_chat()
    await test_tool_calling()
    await test_weather_tool()
    await test_skill()
    await test_guardrail()
    await test_multi_tool()

    separator("全部测试完成 🎉")


if __name__ == "__main__":
    asyncio.run(main())
