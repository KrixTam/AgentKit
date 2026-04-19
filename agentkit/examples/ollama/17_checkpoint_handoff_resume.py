"""
示例 17：Checkpoint + Handoff + Resume（执行指针恢复，Ollama 目录版）
"""
from __future__ import annotations

import os
import sys
import asyncio
from typing import AsyncGenerator

# 与其它 Ollama 示例保持一致，确保本地源码可直接导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit.agents.base_agent import BaseAgent
from agentkit.runner.context import RunContext
from agentkit.runner.context_store import InMemoryContextStore
from agentkit.runner.events import Event, EventType
from agentkit.runner.runner import Runner


class ReviewAgent(BaseAgent):
    async def _run_impl(self, ctx: RunContext) -> AsyncGenerator[Event, None]:
        if not ctx.state.get("review_suspended_once"):
            ctx.state["review_suspended_once"] = True
            ctx.state["__suspended_tool_call_id__"] = "manual-review-1"
            ctx.state["__suspended_tool_name__"] = "manual_review"
            yield Event(
                agent=self.name,
                type=EventType.SUSPEND_REQUESTED,
                data={"prompt": "请审批该任务（approve/reject）", "tool": "manual_review", "tool_call_id": "manual-review-1"},
            )
            return

        tool_msgs = [m for m in ctx.messages if m.get("role") == "tool" and m.get("tool_call_id") == "manual-review-1"]
        decision = tool_msgs[-1].get("content", "unknown") if tool_msgs else "unknown"
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=f"Review completed: {decision}")


class RootAgent(BaseAgent):
    async def _run_impl(self, ctx: RunContext) -> AsyncGenerator[Event, None]:
        yield Event(agent=self.name, type=EventType.HANDOFF, data={"target": "reviewer"})


async def main() -> None:
    root = RootAgent(name="root")
    reviewer = ReviewAgent(name="reviewer")
    root.sub_agents.append(reviewer)
    reviewer.parent_agent = root

    store = InMemoryContextStore()
    session_id = "demo-handoff-checkpoint-001"

    print("=== 阶段 1：运行并挂起 ===")
    async for event in Runner.run_with_checkpoint(
        root,
        input="请审批部署任务",
        session_id=session_id,
        context_store=store,
        max_turns=5,
    ):
        print(f"[run] {event.type} | agent={event.agent} | data={event.data}")

    print("\n=== 阶段 2：恢复并完成 ===")
    async for event in Runner.resume(
        root,
        session_id=session_id,
        user_input="approve",
        context_store=store,
    ):
        print(f"[resume] {event.type} | agent={event.agent} | data={event.data}")


if __name__ == "__main__":
    asyncio.run(main())
