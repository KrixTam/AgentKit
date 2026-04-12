"""
agentkit/agents/sequential_agent.py — 顺序执行子 Agent
agentkit/agents/parallel_agent.py  — 并行执行子 Agent
agentkit/agents/loop_agent.py      — 循环执行子 Agent

编排 Agent 合并在一个文件中。
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncGenerator

from ..runner.events import Event
from .base_agent import BaseAgent

if TYPE_CHECKING:
    from ..runner.context import RunContext


class SequentialAgent(BaseAgent):
    """按顺序执行子 Agent"""

    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        for sub in self.sub_agents:
            async for event in sub.run(ctx):
                yield event
                if event.type == "escalate":
                    return


class ParallelAgent(BaseAgent):
    """并行执行子 Agent（分支隔离）"""

    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        async def collect(agent: BaseAgent, branch_ctx: "RunContext") -> list[Event]:
            events: list[Event] = []
            async for event in agent.run(branch_ctx):
                events.append(event)
            return events

        tasks = [
            collect(sub, ctx.create_branch(sub.name))
            for sub in self.sub_agents
        ]
        results = await asyncio.gather(*tasks)
        for events in results:
            for event in events:
                yield event


class LoopAgent(BaseAgent):
    """循环执行子 Agent，直到 escalate 或达到 max_iterations"""

    max_iterations: int = 10

    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        for _ in range(self.max_iterations):
            for sub in self.sub_agents:
                async for event in sub.run(ctx):
                    yield event
                    if event.type == "escalate":
                        return
