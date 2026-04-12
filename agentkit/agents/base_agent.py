"""
agentkit/agents/base_agent.py — 所有 Agent 的基类

模板方法模式：run() 是 final 的，子类实现 _run_impl()。
"""
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..runner.events import Event

if TYPE_CHECKING:
    from ..runner.context import RunContext


class BaseAgent(BaseModel):
    """所有 Agent 的基类"""

    name: str
    description: str = ""
    parent_agent: Optional["BaseAgent"] = None
    sub_agents: list["BaseAgent"] = Field(default_factory=list)
    before_agent_callback: Optional[Callable] = None
    after_agent_callback: Optional[Callable] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_post_init(self, __context: Any) -> None:
        for sub in self.sub_agents:
            if sub.parent_agent is not None:
                raise ValueError(f"Agent '{sub.name}' 已有父 Agent")
            sub.parent_agent = self

    async def run(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        """运行入口 — 子类不可覆盖"""
        # 1. before callback
        if self.before_agent_callback:
            result = await self.before_agent_callback(ctx)
            if result is not None:
                yield Event(agent=self.name, type="callback", data=result)
                return

        # 2. 核心逻辑（子类实现）
        async for event in self._run_impl(ctx):
            yield event

        # 3. after callback
        if self.after_agent_callback:
            result = await self.after_agent_callback(ctx)
            if result is not None:
                yield Event(agent=self.name, type="callback", data=result)

    @abstractmethod
    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        raise NotImplementedError
        yield  # type: ignore  # pragma: no cover
