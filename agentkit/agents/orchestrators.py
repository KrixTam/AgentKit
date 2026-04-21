"""
agentkit/agents/sequential_agent.py — 顺序执行子 Agent
agentkit/agents/parallel_agent.py  — 并行执行子 Agent
agentkit/agents/loop_agent.py      — 循环执行子 Agent

编排 Agent 合并在一个文件中。
"""
from __future__ import annotations

import asyncio
from contextlib import aclosing
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable

from ..runner.events import Event
from .base_agent import BaseAgent

if TYPE_CHECKING:
    from ..runner.context import RunContext


class SequentialAgent(BaseAgent):
    """按顺序执行子 Agent"""

    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        for sub in self.sub_agents:
            async with aclosing(sub.run(ctx)) as stream:
                async for event in stream:
                    yield event
                    if event.type == "escalate":
                        return


class ParallelAgent(BaseAgent):
    """并行执行子 Agent（分支隔离）"""

    early_exit: bool = False

    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        if not self.early_exit:
            # 默认行为保持不变
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
            return

        # 增强模式：支持 early_exit
        branch_status: dict[str, str] = {sub.name: "pending" for sub in self.sub_agents}
        all_events: dict[str, list[Event]] = {sub.name: [] for sub in self.sub_agents}
        queue: asyncio.Queue[tuple[str, Event]] = asyncio.Queue()

        async def run_branch(agent: BaseAgent, branch_ctx: "RunContext") -> None:
            branch_status[agent.name] = "running"
            try:
                async with aclosing(agent.run(branch_ctx)) as stream:
                    async for event in stream:
                        all_events[agent.name].append(event)
                        await queue.put((agent.name, event))
                        if event.type == "escalate":
                            branch_status[agent.name] = "escalated"
                            return
                branch_status[agent.name] = "completed"
            except asyncio.CancelledError:
                branch_status[agent.name] = "cancelled"

        tasks = {
            sub.name: asyncio.create_task(run_branch(sub, ctx.create_branch(sub.name)))
            for sub in self.sub_agents
        }

        early_exit_triggered_by: str | None = None

        while any(not t.done() for t in tasks.values()) or not queue.empty():
            try:
                # Use a small timeout to periodically check task completion if queue is empty
                name, event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield event
                
                if event.type == "escalate" and not early_exit_triggered_by:
                    early_exit_triggered_by = name
                    for t_name, t in tasks.items():
                        if t_name != name and not t.done():
                            t.cancel()
            except asyncio.TimeoutError:
                continue

        if early_exit_triggered_by:
            yield Event(
                agent=self.name,
                type="parallel_early_exit",
                data={
                    "reason": f"Branch '{early_exit_triggered_by}' escalated.",
                    "branch_status": branch_status
                }
            )


class LoopAgent(BaseAgent):
    """循环执行子 Agent，直到 escalate 或达到 max_iterations"""

    max_iterations: int = 10
    # Keep runtime annotation simple to avoid Pydantic forward-ref rebuild errors.
    loop_condition: Callable[[Any, Any], bool] | None = None

    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        for iteration in range(self.max_iterations):
            for sub in self.sub_agents:
                async with aclosing(sub.run(ctx)) as stream:
                    async for event in stream:
                        yield event
                        if event.type == "escalate":
                            return

            if self.loop_condition is not None:
                # Provide ctx and current iteration index (0-based) as state
                if not self.loop_condition(ctx, {"iteration": iteration}):
                    yield Event(
                        agent=self.name,
                        type="loop_exit",
                        data={"reason": "loop_condition_met", "iteration": iteration + 1}
                    )
                    return

        # Enhanced: loop exhausted event
        yield Event(
            agent=self.name,
            type="loop_exhausted",
            data={
                "reason": f"Reached max_iterations ({self.max_iterations})",
                "last_iteration": self.max_iterations
            }
        )
