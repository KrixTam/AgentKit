"""
示例 3：带 Skill 的 Agent — 领域知识包

演示 Skill 的核心用法：
- 代码中定义 Skill（Frontmatter + Instructions）
- Skill 三级渐进式加载（L1 → L2 → L3）
- Skill 与 Tool 的协作

运行前请设置环境变量：
  export OPENAI_API_KEY="sk-..."

运行：
  python examples/standard/03_skill_usage.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner, Skill, SkillFrontmatter, SkillResources, function_tool


# ===== 定义工具 =====

@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    weather_data = {
        "北京": "晴，25°C",
        "上海": "多云，22°C",
        "深圳": "阵雨，28°C",
        "广州": "晴，30°C",
        "成都": "阴，18°C",
    }
    return weather_data.get(city, f"{city}：暂无数据")


# ===== 定义 Skill =====

weather_skill = Skill(
    frontmatter=SkillFrontmatter(
        name="weather-analysis",
        description="天气分析技能，查询天气并给出穿衣建议",
    ),
    instructions="""## 天气分析步骤

1. 使用 get_weather 工具查询用户指定城市的天气
2. 根据天气情况给出穿衣建议：
   - 温度 > 30°C：建议穿短袖、注意防晒
   - 温度 20-30°C：建议穿薄外套
   - 温度 < 20°C：建议穿厚外套
3. 如果有雨，额外提醒带伞
4. 用简洁的中文回复用户""",
)


# ===== 创建带 Skill 的 Agent =====

agent = Agent(
    name="skill-agent",
    instructions="你是一个智能助手，可以使用专业技能来完成任务。",
    model="gpt-4o",
    skills=[weather_skill],       # ⭐ Skill 作为一等公民
    tools=[get_weather],
)


# ===== 运行测试 =====

queries = [
    "深圳今天适合穿什么衣服？",
    "成都现在冷不冷？需要穿什么？",
    "广州今天出门要注意什么？",
]

for q in queries:
    print(f"\n用户: {q}")
    result = Runner.run_sync(agent, input=q)
    if result.success:
        print(f"助手: {result.final_output}")
    else:
        print(f"❌ 错误: {result.error}")

    # 展示 Skill 和工具调用
    for event in result.events:
        if event.type == "tool_result":
            tool_name = event.data.get("tool", "")
            if tool_name == "load_skill":
                print(f"  📚 加载了 Skill: {event.data.get('result', {}).get('skill_name', '')}")
            else:
                print(f"  🔧 工具调用: {event.data}")
