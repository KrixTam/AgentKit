from __future__ import annotations

import asyncio

from agentkit.agents.base_agent import BaseAgent
from agentkit.agents.orchestrators import ParallelAgent
from agentkit.runner.context import RunContext
from agentkit.runner.context_store import InMemoryContextStore
from agentkit.runner.events import Event, EventType
from agentkit.runner.runner import Runner


class SuspendThenFinishAgent(BaseAgent):
    async def _run_impl(self, ctx):
        resumed_input = None
        for msg in ctx.messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == "approve-call-1":
                resumed_input = msg.get("content")
                break

        if resumed_input is None:
            yield Event(
                agent=self.name,
                type=EventType.SUSPEND_REQUESTED,
                data={
                    "tool_call_id": "approve-call-1",
                    "tool": "manual_approve",
                    "prompt": "请人工确认",
                    "resume_strategy": "as_tool_result",
                },
            )
            return

        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=f"approved:{resumed_input}")


class TwoStageSuspendAgent(BaseAgent):
    async def _run_impl(self, ctx):
        first_done = any(
            msg.get("role") == "tool" and msg.get("tool_call_id") == "gate-1"
            for msg in ctx.messages
        )
        if not first_done:
            yield Event(
                agent=self.name,
                type=EventType.SUSPEND_REQUESTED,
                data={"tool_call_id": "gate-1", "tool": "manual_gate", "prompt": "first gate"},
            )
            return

        yield Event(
            agent=self.name,
            type=EventType.SUSPEND_REQUESTED,
            data={"tool_call_id": "gate-2", "tool": "manual_gate", "prompt": "second gate"},
        )


class SlowAgent(BaseAgent):
    async def _run_impl(self, ctx):
        await asyncio.sleep(0.2)
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data="slow_done")


class EscalateAgent(BaseAgent):
    async def _run_impl(self, ctx):
        yield Event(agent=self.name, type=EventType.ESCALATE, data="fatal")


def test_checkpoint_suspend_resume_roundtrip():
    async def _case():
        agent = SuspendThenFinishAgent(name="ops")
        store = InMemoryContextStore()
        session_id = "s-checkpoint-1"

        events = [e async for e in Runner.run_with_checkpoint(agent, input="deploy", session_id=session_id, context_store=store)]
        assert events[0].type == EventType.SUSPEND_REQUESTED
        assert events[0].data["suspension_id"]
        assert events[1].type == "suspended"

        suspension_id = events[0].data["suspension_id"]
        resumed = [
            e
            async for e in Runner.resume(
                agent,
                session_id=session_id,
                user_input="yes",
                context_store=store,
                suspension_id=suspension_id,
            )
        ]
        assert resumed[0].type == EventType.HUMAN_INPUT_RECEIVED
        assert resumed[-1].type == EventType.FINAL_OUTPUT
        assert resumed[-1].data == "approved:yes"

    asyncio.run(_case())


def test_resume_idempotency_key_duplicate_ignored():
    async def _case():
        agent = TwoStageSuspendAgent(name="ops")
        store = InMemoryContextStore()
        session_id = "s-checkpoint-2"

        first_run = [e async for e in Runner.run_with_checkpoint(agent, input="start", session_id=session_id, context_store=store)]
        suspension_id = first_run[0].data["suspension_id"]

        first_resume = [
            e
            async for e in Runner.resume(
                agent,
                session_id=session_id,
                user_input="ok",
                context_store=store,
                suspension_id=suspension_id,
                idempotency_key="idem-1",
            )
        ]
        assert any(e.type == "suspended" for e in first_resume)

        duplicate_resume = [
            e
            async for e in Runner.resume(
                agent,
                session_id=session_id,
                user_input="ok",
                context_store=store,
                suspension_id=suspension_id,
                idempotency_key="idem-1",
            )
        ]
        assert len(duplicate_resume) == 1
        assert duplicate_resume[0].type == EventType.HUMAN_INPUT_RECEIVED
        assert duplicate_resume[0].data["status"] == "duplicate_ignored"

    asyncio.run(_case())


def test_parallel_early_exit_emits_branch_status():
    async def _case():
        parallel = ParallelAgent(
            name="parallel",
            early_exit=True,
            sub_agents=[SlowAgent(name="slow"), EscalateAgent(name="fast")],
        )
        events = [e async for e in parallel.run(RunContext(input="x"))]
        summary = next(e for e in events if e.type == "parallel_early_exit")
        status = summary.data["branch_status"]

        assert status["fast"] == "escalated"
        assert status["slow"] in {"cancelled", "completed"}

    asyncio.run(_case())
