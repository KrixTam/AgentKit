"""
示例 6：编排 Agent — 顺序执行、并行执行、循环执行

演示三种编排模式：
- SequentialAgent：按顺序执行子 Agent（流水线）
- ParallelAgent：并行执行子 Agent（分支隔离）
- LoopAgent：循环执行直到 escalate 或达到上限

运行前请设置环境变量：
  export OPENAI_API_KEY="sk-..."

运行：
  python examples/standard/06_orchestration.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner, SequentialAgent, ParallelAgent, LoopAgent


# ============================================================
# 模式 A：顺序执行 — 报告生成流水线
# ============================================================

print("=" * 50)
print("  SequentialAgent — 报告生成流水线")
print("=" * 50)

pipeline = SequentialAgent(
    name="report-pipeline",
    sub_agents=[
        Agent(
            name="extractor",
            instructions="你是数据提取专家。从用户输入中提取所有关键数据点，以列表形式输出。",
            model="gpt-4o",
        ),
        Agent(
            name="analyzer",
            instructions="你是数据分析专家。分析上文提取的数据点，找出趋势和规律，给出 2-3 条洞察。",
            model="gpt-4o",
        ),
        Agent(
            name="reporter",
            instructions="你是报告撰写专家。将上文的分析结果写成一段简洁的中文报告（不超过 100 字）。",
            model="gpt-4o",
        ),
    ],
)

result = Runner.run_sync(pipeline, input="今年Q1销售额1000万，Q2增长到1500万，Q3下降到1200万，Q4预计1800万")
print(f"\n输入: 今年Q1销售额1000万...")
for event in result.events:
    if event.type == "final_output":
        print(f"  [{event.agent}] {event.data}")


# ============================================================
# 模式 B：并行执行 — 多维度分析
# ============================================================

print(f"\n{'=' * 50}")
print("  ParallelAgent — 多维度并行分析")
print("=" * 50)

parallel = ParallelAgent(
    name="multi-analysis",
    sub_agents=[
        Agent(
            name="financial",
            instructions="你是财务分析师。用一句话分析给定数据的财务状况。",
            model="gpt-4o",
        ),
        Agent(
            name="market",
            instructions="你是市场分析师。用一句话分析给定数据反映的市场趋势。",
            model="gpt-4o",
        ),
        Agent(
            name="risk",
            instructions="你是风险分析师。用一句话分析给定数据中的潜在风险。",
            model="gpt-4o",
        ),
    ],
)

result = Runner.run_sync(parallel, input="公司年收入 5 亿，同比增长 20%，但负债率从 30% 升至 45%")
print(f"\n输入: 公司年收入 5 亿...")
for event in result.events:
    if event.type == "final_output":
        print(f"  [{event.agent}] {event.data}")


# ============================================================
# 模式 C：循环执行 — 迭代优化
# ============================================================

print(f"\n{'=' * 50}")
print("  LoopAgent — 迭代优化循环")
print("=" * 50)

loop = LoopAgent(
    name="improvement-loop",
    max_iterations=3,
    sub_agents=[
        Agent(
            name="writer",
            instructions="你是一个文案写手。根据用户需求或上轮反馈，写一句广告语。只输出广告语本身。",
            model="gpt-4o",
        ),
        Agent(
            name="critic",
            instructions="你是一个文案评审。评估上面的广告语，如果已经很好则只输出'通过'，否则给出简短的改进建议。",
            model="gpt-4o",
        ),
    ],
)

result = Runner.run_sync(loop, input="为一款AI编程助手写一句吸引开发者的广告语")
print(f"\n输入: 为一款AI编程助手写广告语")
for event in result.events:
    if event.type == "final_output":
        print(f"  [{event.agent}] {event.data}")
