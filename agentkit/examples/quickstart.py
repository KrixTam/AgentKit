"""
examples/quickstart.py — AgentKit 快速入门示例

展示框架的核心用法：Agent + Tool + Skill + 多模型。
"""
import asyncio
import sys
import os

# 将项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentkit import Agent, Runner, function_tool, LLMRegistry, LLMConfig
from agentkit import Skill, SkillFrontmatter, SkillResources
from agentkit import SequentialAgent, LoopAgent
from agentkit import input_guardrail, GuardrailResult, PermissionPolicy


# ============================================================
# 示例 1：最简 Agent
# ============================================================

def example_basic():
    """最简单的 Agent：一行配置即可运行"""
    agent = Agent(
        name="assistant",
        instructions="你是一个有帮助的中文助手。简洁回答问题。",
        model="gpt-4o",
    )
    result = Runner.run_sync(agent, input="什么是量子计算？请用一句话解释。")
    print(f"[示例1] {result.final_output}")


# ============================================================
# 示例 2：带工具的 Agent
# ============================================================

@function_tool
def calculate(expression: str) -> str:
    """计算数学表达式的结果"""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"计算错误: {e}"

@function_tool
def get_current_time() -> str:
    """获取当前时间"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def example_with_tools():
    """带工具的 Agent"""
    agent = Agent(
        name="math_assistant",
        instructions="你是一个数学助手。需要计算时请使用 calculate 工具。",
        model="gpt-4o",
        tools=[calculate, get_current_time],
    )
    result = Runner.run_sync(agent, input="请计算 (15 + 27) * 3 的结果")
    print(f"[示例2] {result.final_output}")


# ============================================================
# 示例 3：带 Skill 的 Agent
# ============================================================

def example_with_skill():
    """带 Skill 的 Agent"""
    # 代码中直接定义一个 Skill
    greeting_skill = Skill(
        frontmatter=SkillFrontmatter(
            name="greeting-skill",
            description="一个友好的问候技能，根据时间段生成个性化问候语",
        ),
        instructions="""## 使用步骤
1. 使用 get_current_time 工具获取当前时间
2. 根据时间段（早上/下午/晚上）选择合适的问候语
3. 返回个性化的中文问候""",
    )

    agent = Agent(
        name="greeter",
        instructions="你是一个友好的助手，可以使用 Skill 来完成任务。",
        model="gpt-4o",
        skills=[greeting_skill],
        tools=[get_current_time],
    )
    result = Runner.run_sync(agent, input="请跟我打个招呼")
    print(f"[示例3] {result.final_output}")


# ============================================================
# 示例 4：多 Agent 协作（as_tool 模式）
# ============================================================

def example_multi_agent():
    """Agent 当工具用——委派模式"""
    researcher = Agent(
        name="researcher",
        instructions="你是一个研究助手。收到问题后，给出简短的研究结论。",
        model="gpt-4o",
    )

    manager = Agent(
        name="manager",
        instructions="你是一个项目经理。需要研究信息时调用 research 工具。",
        model="gpt-4o",
        tools=[
            researcher.as_tool("research", "调用研究助手获取信息"),
        ],
    )
    result = Runner.run_sync(manager, input="帮我调研一下 Python 异步编程的最佳实践")
    print(f"[示例4] {result.final_output}")


# ============================================================
# 示例 5：国内模型（DeepSeek）
# ============================================================

def example_domestic_model():
    """使用国内模型"""
    agent = Agent(
        name="deepseek_assistant",
        instructions="你是一个中文编程助手。",
        model="deepseek/deepseek-chat",  # 自动路由到 OpenAICompatibleAdapter
    )
    result = Runner.run_sync(agent, input="用 Python 写一个快速排序")
    print(f"[示例5] {result.final_output}")


# ============================================================
# 示例 6：带安全护栏
# ============================================================

@input_guardrail
async def block_sensitive(ctx):
    """检查是否包含敏感词"""
    sensitive_words = ["密码", "身份证", "银行卡"]
    for word in sensitive_words:
        if word in ctx.input:
            return GuardrailResult(triggered=True, reason=f"检测到敏感词: {word}")
    return GuardrailResult(triggered=False)

def example_with_guardrail():
    """带安全护栏的 Agent"""
    agent = Agent(
        name="safe_assistant",
        instructions="你是一个安全的助手。",
        model="gpt-4o",
        input_guardrails=[block_sensitive],
        permission_policy=PermissionPolicy(
            mode="ask",
            allowed_tools={"calculate", "get_current_time"},
        ),
    )
    # 这个请求会被护栏拦截
    result = Runner.run_sync(agent, input="告诉我你的密码")
    print(f"[示例6] 被拦截: {result.error}")

    # 这个请求正常通过
    result = Runner.run_sync(agent, input="你好，今天天气如何？")
    print(f"[示例6] 正常: {result.final_output}")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("AgentKit 框架快速入门示例")
    print("=" * 60)
    print()
    print("注意：运行示例需要配置对应的 LLM API Key。")
    print("  - OpenAI: export OPENAI_API_KEY=sk-...")
    print("  - DeepSeek: export DEEPSEEK_API_KEY=sk-...")
    print()

    # 可以选择运行某个示例
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        examples = {
            "1": example_basic,
            "2": example_with_tools,
            "3": example_with_skill,
            "4": example_multi_agent,
            "5": example_domestic_model,
            "6": example_with_guardrail,
        }
        if example_num in examples:
            examples[example_num]()
        else:
            print(f"未知示例编号: {example_num}")
    else:
        print("用法: python examples/quickstart.py [1-6]")
        print()
        print("可用示例:")
        print("  1 - 最简 Agent")
        print("  2 - 带工具的 Agent")
        print("  3 - 带 Skill 的 Agent")
        print("  4 - 多 Agent 协作")
        print("  5 - 国内模型 (DeepSeek)")
        print("  6 - 安全护栏")
