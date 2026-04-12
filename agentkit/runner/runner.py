"""
agentkit/runner/runner.py — Runner 核心循环

驱动 Agent 的 turn-by-turn 执行循环。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator

from .context import RunContext
from .events import Event, RunResult

logger = logging.getLogger("agentkit.runner")


class MaxTurnsExceeded(Exception):
    pass


class Runner:
    """Agent 运行引擎"""

    @classmethod
    async def run(
        cls,
        agent: Any,
        *,
        input: str,
        context: Any = None,
        user_id: str | None = None,
        max_turns: int = 10,
    ) -> RunResult:
        ctx = RunContext(input=input, shared_context=context, user_id=user_id)
        current_agent = agent
        events: list[Event] = []

        for turn in range(max_turns):
            # 输入护栏
            if hasattr(current_agent, "input_guardrails"):
                for guardrail in current_agent.input_guardrails:
                    result = await guardrail.check(ctx)
                    if result.triggered:
                        return RunResult(error=f"输入被安全护栏拦截: {result.reason}", events=events)

            # 执行 Agent
            async for event in current_agent.run(ctx):
                events.append(event)

                if event.type == "final_output":
                    # 输出护栏
                    if hasattr(current_agent, "output_guardrails"):
                        for guardrail in current_agent.output_guardrails:
                            result = await guardrail.check(ctx, event.data)
                            if result.triggered:
                                return RunResult(error=f"输出被安全护栏拦截: {result.reason}", events=events)

                    return RunResult(
                        final_output=event.data,
                        events=events,
                        last_agent=current_agent.name,
                    )

                if event.type == "handoff":
                    target_name = event.data.get("target", "")
                    new_agent = cls._find_agent(agent, target_name)
                    if new_agent:
                        current_agent = new_agent
                        break
                    else:
                        return RunResult(error=f"Handoff 目标 '{target_name}' 未找到", events=events)

                if event.type == "error":
                    return RunResult(error=str(event.data), events=events)

        return RunResult(error=f"超过最大轮次 {max_turns}", events=events)

    @classmethod
    def run_sync(cls, agent: Any, **kwargs: Any) -> RunResult:
        """同步运行"""
        return asyncio.run(cls.run(agent, **kwargs))

    @classmethod
    async def run_streamed(cls, agent: Any, *, input: str, **kwargs: Any) -> AsyncGenerator[Event, None]:
        """流式运行，实时产出 Event"""
        ctx = RunContext(input=input, **kwargs)
        async for event in agent.run(ctx):
            yield event

    @staticmethod
    def _find_agent(root: Any, name: str) -> Any | None:
        """在 Agent 树中查找指定名称的 Agent"""
        if root.name == name:
            return root
        if hasattr(root, "sub_agents"):
            for sub in root.sub_agents:
                found = Runner._find_agent(sub, name)
                if found:
                    return found
        if hasattr(root, "handoffs"):
            for h in root.handoffs:
                if hasattr(h, "name") and h.name == name:
                    return h
        return None
