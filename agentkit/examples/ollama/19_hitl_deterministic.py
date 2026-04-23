"""
示例 19（Playground/HITL 专用）：确定性触发挂起（必现）

用途：
- 提供一个可被 AgentHub `entry` 直接加载的 `agent` 实例；
- 首次运行必然发出 `suspend_requested`，便于 Playground 稳定演示 HITL 闭环。
"""
from __future__ import annotations

import os
import sys
from typing import AsyncGenerator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit.agents.base_agent import BaseAgent
from agentkit.runner.context import RunContext
from agentkit.runner.events import Event, EventType


class DeterministicHITLAgent(BaseAgent):
    async def _run_impl(self, ctx: RunContext) -> AsyncGenerator[Event, None]:
        # 第一次进入会话时，确定性触发挂起。
        if not ctx.state.get("deterministic_hitl_suspended_once"):
            ctx.state["deterministic_hitl_suspended_once"] = True
            suspension = ctx.register_suspension(
                tool_call_id="det-hitl-1",
                tool_name="manual_approval",
                prompt="请审批该操作（approve/reject）",
            )
            yield Event(
                agent=self.name,
                type=EventType.SUSPEND_REQUESTED,
                data={
                    "suspension_id": suspension.suspension_id,
                    "prompt": "请审批该操作（approve/reject）",
                    "tool": "manual_approval",
                    "tool_call_id": "det-hitl-1",
                },
            )
            return

        decision = "unknown"
        for msg in reversed(ctx.messages):
            if msg.get("role") == "tool" and msg.get("tool_call_id") == "det-hitl-1":
                decision = msg.get("content", "unknown")
                break

        yield Event(
            agent=self.name,
            type=EventType.FINAL_OUTPUT,
            data=f"已收到人工决策: {decision}",
        )


agent = DeterministicHITLAgent(name="deterministic-hitl-agent")

