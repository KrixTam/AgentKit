from __future__ import annotations

import asyncio

from agentkit.agents.base_agent import BaseAgent
from agentkit.agents.orchestrators import LoopAgent, SequentialAgent
from agentkit.runner.context import RunContext
from agentkit.runner.events import Event


class EscalateAgent(BaseAgent):
    async def _run_impl(self, ctx):
        yield Event(agent=self.name, type="escalate", data="stop")


class TwoStepAgent(BaseAgent):
    async def _run_impl(self, ctx):
        yield Event(agent=self.name, type="llm_response", data="step1")
        yield Event(agent=self.name, type="final_output", data="done")


def test_after_callback_triggered_for_single_loop_agent():
    async def _case():
        called: list[str] = []
        loop = LoopAgent(
            name="loop",
            sub_agents=[EscalateAgent(name="sub")],
            after_agent_callback=lambda _ctx: called.append("loop_after"),
        )
        async for _ in loop.run(RunContext(input="x")):
            pass
        assert called == ["loop_after"]

    asyncio.run(_case())


def test_after_callback_triggered_for_loop_agent_under_sequential():
    async def _case():
        called: list[str] = []
        loop = LoopAgent(
            name="loop",
            sub_agents=[EscalateAgent(name="sub")],
            after_agent_callback=lambda _ctx: called.append("loop_after"),
        )
        seq = SequentialAgent(name="seq", sub_agents=[loop])
        async for _ in seq.run(RunContext(input="x")):
            pass
        assert called == ["loop_after"]

    asyncio.run(_case())


def test_after_callback_triggered_when_child_generator_closed_early():
    async def _case():
        called: list[str] = []
        child = TwoStepAgent(
            name="child",
            after_agent_callback=lambda _ctx: called.append("child_after"),
        )
        seq = SequentialAgent(name="seq", sub_agents=[child])

        stream = seq.run(RunContext(input="x"))
        await stream.__anext__()
        await stream.aclose()

        # 显式关闭父生成器后，子生成器 finally 链路必须执行
        assert called == ["child_after"]

    asyncio.run(_case())
