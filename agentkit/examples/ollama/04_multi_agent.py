"""
示例 4：多 Agent 协作 — Handoff 与 as_tool（Ollama 本地版）

演示两种 Agent 协作模式。

运行前请确保 Ollama 已启动：
  ollama serve
  ollama pull qwen3.5:cloud

运行：
  python examples/ollama/04_multi_agent.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner


# ============================================================
# 模式 A：as_tool（委派）
# ============================================================

print("=" * 50)
print("  模式 A：as_tool（委派）")
print("=" * 50)

researcher = Agent(
    name="researcher",
    instructions="你是一个研究助手。收到问题后，给出简短的研究结论（不超过 3 句话）。",
    model="ollama/qwen3.5:cloud",
)

manager = Agent(
    name="manager",
    instructions="你是项目经理。需要研究信息时调用 research 工具。综合研究结果给出你的建议。",
    model="ollama/qwen3.5:cloud",
    tools=[
        researcher.as_tool("research", "调用研究助手获取研究信息"),
    ],
)

result = Runner.run_sync(manager, input="帮我调研 Python 异步编程的最佳实践")
if result.success:
    print(f"\n✅ 回复: {result.final_output}")
else:
    print(f"\n❌ 错误: {result.error}")

for event in result.events:
    if event.type == "tool_result":
        print(f"  🔧 研究员返回: {str(event.data)[:100]}")


# ============================================================
# 模式 B：Handoff（转介）
# ============================================================

print(f"\n{'=' * 50}")
print("  模式 B：Handoff（转介）")
print("=" * 50)

billing_agent = Agent(
    name="billing",
    instructions="你是账单专家。处理所有账单相关的问题，给出专业的解答。",
    model="ollama/qwen3.5:cloud",
)

tech_agent = Agent(
    name="tech",
    instructions="你是技术支持专家。处理所有技术相关的问题。",
    model="ollama/qwen3.5:cloud",
)

triage_agent = Agent(
    name="triage",
    instructions="你是客服分诊员。根据用户问题类型，转交给合适的专家：账单问题转给 billing，技术问题转给 tech。",
    model="ollama/qwen3.5:cloud",
    handoffs=[billing_agent, tech_agent],
)

result = Runner.run_sync(triage_agent, input="我的账单金额好像不对，比上个月多了很多")
if result.success:
    print(f"\n✅ 最终由 [{result.last_agent}] 处理: {result.final_output}")
else:
    print(f"\n❌ 错误: {result.error}")
