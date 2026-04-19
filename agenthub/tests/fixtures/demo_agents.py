from __future__ import annotations

from typing import AsyncGenerator

from agentkit.agents.base_agent import BaseAgent
from agentkit.runner.events import Event, EventType


class EchoAgent(BaseAgent):
    async def _run_impl(self, ctx) -> AsyncGenerator[Event, None]:
        yield Event(agent=self.name, type=EventType.LLM_RESPONSE, data={"echo": ctx.input})
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=f"echo:{ctx.input}")


class HitlAgent(BaseAgent):
    async def _run_impl(self, ctx) -> AsyncGenerator[Event, None]:
        if ctx.state.get("_hitl_resumed"):
            yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data="approved")
            return
        ctx.state["_hitl_resumed"] = True
        yield Event(
            agent=self.name,
            type=EventType.SUSPEND_REQUESTED,
            data={
                "prompt": "please approve",
                "form_schema": {
                    "type": "object",
                    "properties": {"user_input": {"type": "string"}},
                    "required": ["user_input"],
                },
            },
        )


def create_echo_agent():
    return EchoAgent(name="demo-echo")


def create_hitl_agent():
    return HitlAgent(name="demo-hitl")
