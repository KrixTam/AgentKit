from __future__ import annotations

from typing import AsyncGenerator

from agentkit.agents.base_agent import BaseAgent
from agentkit.runner.events import Event, EventType


class EchoAgent(BaseAgent):
    async def _run_impl(self, ctx) -> AsyncGenerator[Event, None]:
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=f"echo:{ctx.input}")


def create_agent() -> BaseAgent:
    return EchoAgent(name="demo-echo")
