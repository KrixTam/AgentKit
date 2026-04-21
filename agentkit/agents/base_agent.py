"""
agentkit/agents/base_agent.py — 所有 Agent 的基类

模板方法模式：run() 是 final 的，子类实现 _run_impl()。
"""
from __future__ import annotations

import asyncio
from abc import abstractmethod
from contextlib import aclosing
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
    fail_fast_on_hook_error: bool = False
    model_cosplay_enabled: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    async def _run_hook(self, hook: Optional[Callable], _hook_name: str, *args, **kwargs) -> tuple[Any, float, Optional[Exception]]:
        """执行回调钩子并返回 (结果, 耗时(秒), 异常)"""
        if not hook:
            return None, 0.0, None
        
        import time
        import inspect
        start_time = time.time()
        try:
            result = hook(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            duration = time.time() - start_time
            return result, duration, None
        except Exception as e:
            duration = time.time() - start_time
            return None, duration, e

    def model_post_init(self, _context: Any) -> None:
        for sub in self.sub_agents:
            if sub.parent_agent is not None:
                raise ValueError(f"Agent '{sub.name}' 已有父 Agent")
            sub.parent_agent = self

    def apply_model_cosplay(self, model_override: Any) -> "BaseAgent":
        """尝试对当前 Agent 应用模型伪装（默认不支持）。"""
        if model_override in (None, ""):
            return self
        raise ValueError(f"Agent '{self.name}' 不支持 ModelCosplay")

    async def run(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        """运行入口 — 子类不可覆盖"""
        emit_after_events = True
        try:
            # 1. before callback
            if self.before_agent_callback:
                result, duration, err = await self._run_hook(self.before_agent_callback, "before_agent_callback", ctx)
                if err:
                    yield Event(agent=self.name, type="error", data={"hook": "before_agent", "error": str(err), "duration": duration})
                    if self.fail_fast_on_hook_error:
                        return
                elif result is not None:
                    yield Event(agent=self.name, type="callback", data={"result": result, "duration": duration})
                    return

            # 2. 核心逻辑（子类实现）
            impl_stream = self._run_impl(ctx)
            async with aclosing(impl_stream):
                async for event in impl_stream:
                    yield event
        except (GeneratorExit, asyncio.CancelledError):
            # 外部提前中断时不再尝试向外 yield 事件，但必须执行 after 回调逻辑
            emit_after_events = False
            raise
        finally:
            # 3. after callback（保证执行）
            if self.after_agent_callback:
                result, duration, err = await self._run_hook(self.after_agent_callback, "after_agent_callback", ctx)
                if emit_after_events:
                    if err:
                        yield Event(agent=self.name, type="error", data={"hook": "after_agent", "error": str(err), "duration": duration})
                    elif result is not None:
                        yield Event(agent=self.name, type="callback", data={"result": result, "duration": duration})

    @abstractmethod
    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        raise NotImplementedError
        yield  # type: ignore  # pragma: no cover
