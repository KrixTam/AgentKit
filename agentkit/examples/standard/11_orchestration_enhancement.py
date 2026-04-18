import asyncio
import sys
import os

# 确保能导入 agentkit
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from agentkit import Agent, Runner, LoopAgent, ParallelAgent
from agentkit.runner.events import Event
from agentkit.agents.base_agent import BaseAgent

# ==========================================
# 1. LoopAgent 增强：基于动态状态提前退出循环
# ==========================================

def loop_exit_condition(ctx, state):
    iteration = state["iteration"]
    if iteration >= 2:
        print(f"[Loop] 动态条件达成，将在第 {iteration} 轮终止循环。")
        return False  # 返回 False 将终止循环，避免无限运行
    return True

loop_agent = LoopAgent(
    name="review-loop",
    max_iterations=5, # 默认最高迭代上限
    loop_condition=loop_exit_condition, # 自定义逻辑钩子
    sub_agents=[
        Agent(
            name="coder", 
            instructions="请说：'我已经优化了一版代码'", 
            model="gpt-4o"
        ),
    ]
)

# ==========================================
# 2. ParallelAgent 增强：一旦有分支异常则提前取消 (early_exit)
# ==========================================

class SlowTaskAgent(BaseAgent):
    """模拟一个耗时的任务，中途如果被取消则输出日志"""
    async def _run_impl(self, ctx):
        print("[Parallel-SlowTask] 慢任务开始，预计需要 3 秒...")
        try:
            await asyncio.sleep(3)
            yield Event(agent=self.name, type="final_output", data="慢任务成功完成")
        except asyncio.CancelledError:
            print("[Parallel-SlowTask] 慢任务被提前取消 (Cancelled)！")

class FastErrorAgent(BaseAgent):
    """模拟一个检查任务，迅速发现致命问题并请求 escalate"""
    async def _run_impl(self, ctx):
        print("[Parallel-FastError] 检查任务执行中，发现致命错误，立即升级 (escalate)！")
        yield Event(agent=self.name, type="escalate", data="发现严重漏洞")

parallel_agent = ParallelAgent(
    name="multi-task-checker",
    early_exit=True, # 开启 early_exit 增强模式
    sub_agents=[
        SlowTaskAgent(name="slow_analyzer"), 
        FastErrorAgent(name="fast_checker")
    ]
)

# ==========================================
# 主运行逻辑
# ==========================================

async def main():
    print("=== 演示 1: LoopAgent 动态循环退出 ===")
    await Runner.run(loop_agent, input="开始代码审查")
    
    print("\n=== 演示 2: ParallelAgent 提前终止取消耗时分支 ===")
    async for event in Runner.run_streamed(parallel_agent, input="启动并行任务"):
        if event.type == "parallel_early_exit":
            print(f"✅ 捕获到提前终止事件: {event.data['reason']}")
            print(f"当前分支状态摘要: {event.data['branch_status']}")

if __name__ == "__main__":
    asyncio.run(main())
