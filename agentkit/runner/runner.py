"""
agentkit/runner/runner.py — Runner 核心循环

驱动 Agent 的 turn-by-turn 执行循环。
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator

from .context import RunContext
from .events import Event, RunResult, EventType

if TYPE_CHECKING:
    from .context_store import ContextStore

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
        session_id: str | None = None,
        max_turns: int = 10,
    ) -> RunResult:
        import uuid
        ctx = RunContext(input=input, shared_context=context, user_id=user_id, session_id=session_id or str(uuid.uuid4()))
        current_agent = agent
        events: list[Event] = []

        for _ in range(max_turns):
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
    async def run_streamed(
        cls, 
        agent: Any, 
        *, 
        input: str, 
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any
    ) -> AsyncGenerator[Event, None]:
        """流式运行，实时产出 Event"""
        import uuid
        ctx = RunContext(input=input, user_id=user_id, session_id=session_id or str(uuid.uuid4()), **kwargs)
        async for event in agent.run(ctx):
            yield event

    @classmethod
    async def run_with_checkpoint(
        cls,
        agent: Any,
        *,
        input: str,
        session_id: str,
        context_store: "ContextStore",
        context: Any = None,
        user_id: str | None = None,
        **_kwargs: Any,
    ) -> AsyncGenerator[Event, None]:
        """
        流式运行（支持挂起与恢复）。
        遇到 HumanInputRequested 等挂起信号时，会将状态保存到 context_store。
        """
        # 如果 context_store 中已有该 session 的状态，应通过 resume 继续，而非新建 run
        existing_ctx = context_store.load(session_id)
        if existing_ctx:
            raise ValueError(f"Session {session_id} already exists in ContextStore. Use resume() instead.")

        ctx = RunContext(input=input, shared_context=context, user_id=user_id, session_id=session_id)

        async for event in agent.run(ctx):
            yield event
            if event.type == EventType.SUSPEND_REQUESTED:
                # 遇到挂起请求，保存状态并停止当前执行
                context_store.save(session_id, ctx)
                return
        
        # 运行结束，可选择清理 Checkpoint
        context_store.delete(session_id)

    @classmethod
    async def resume(
        cls,
        agent: Any,
        *,
        session_id: str,
        user_input: str,
        context_store: "ContextStore",
        shared_context_cls: Any = None,
    ) -> AsyncGenerator[Event, None]:
        """恢复执行被挂起的 Agent 会话"""
        ctx = context_store.load(session_id, shared_context_cls)
        if not ctx:
            yield Event(agent=agent.name, type=EventType.ERROR, data=f"找不到会话 {session_id} 的上下文快照")
            return
            
        yield Event(agent=agent.name, type=EventType.HUMAN_INPUT_RECEIVED, data={"input": user_input})
        
        # 恢复挂起的工具调用
        tool_call_id = ctx.state.pop("__suspended_tool_call_id__", None)
        ctx.state.pop("__suspended_tool_name__", None)
        
        if tool_call_id:
            # 将 user_input 作为该挂起工具调用的结果加入上下文
            ctx.add_tool_result(tool_call_id, str(user_input))
            
        # 重新进入 Agent 循环
        async for event in agent.run(ctx):
            yield event
            if event.type == EventType.SUSPEND_REQUESTED:
                # 再次挂起
                context_store.save(session_id, ctx)
                return
        
        # 运行结束清理
        context_store.delete(session_id)

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
