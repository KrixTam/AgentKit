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
        handoff_agent_cache: dict[str, Any | None] = {}

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
                    if target_name in handoff_agent_cache:
                        new_agent = handoff_agent_cache[target_name]
                    else:
                        new_agent = cls._find_agent(agent, target_name)
                        handoff_agent_cache[target_name] = new_agent
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
        流式运行（支持挂起与恢复），语义对齐 `run` 的 turn-loop。
        在挂起时保存 RunContext + 执行指针（轮次、当前 agent、agent path）。
        """
        existing_ctx = context_store.load(session_id)
        if existing_ctx:
            raise ValueError(f"Session {session_id} already exists in ContextStore. Use resume() instead.")

        ctx = RunContext(input=input, shared_context=context, user_id=user_id, session_id=session_id)
        current_agent = agent
        current_agent_path = cls._find_agent_path(agent, current_agent)
        handoff_agent_cache: dict[str, Any | None] = {}
        max_turns = int(_kwargs.get("max_turns", 10))
        turn = 0

        while turn < max_turns:
            ctx.state["__runner_checkpoint__"] = {
                "turn": turn,
                "max_turns": max_turns,
                "current_agent": getattr(current_agent, "name", ""),
                "agent_path": current_agent_path,
            }
            handoff_switched = False
            async for event in current_agent.run(ctx):
                if event.type == EventType.SUSPEND_REQUESTED:
                    suspension_id = cls._ensure_suspension_record(ctx, current_agent, event)
                    yield event
                    context_store.save(session_id, ctx)
                    yield Event(
                        agent=getattr(current_agent, "name", "runner"),
                        type="suspended",
                        data={
                            "session_id": session_id,
                            "turn": turn,
                            "current_agent": getattr(current_agent, "name", ""),
                            "agent_path": current_agent_path,
                            "suspension_id": suspension_id,
                        },
                    )
                    return
                yield event
                if event.type == EventType.FINAL_OUTPUT:
                    context_store.delete(session_id)
                    return
                if event.type == EventType.ERROR:
                    context_store.delete(session_id)
                    return
                if event.type == EventType.HANDOFF:
                    target_name = ""
                    if isinstance(event.data, dict):
                        target_name = event.data.get("target", "")
                    if target_name in handoff_agent_cache:
                        new_agent = handoff_agent_cache[target_name]
                    else:
                        new_agent = cls._find_agent(agent, target_name)
                        handoff_agent_cache[target_name] = new_agent
                    if not new_agent:
                        yield Event(agent=getattr(current_agent, "name", "runner"), type=EventType.ERROR, data=f"Handoff 目标 '{target_name}' 未找到")
                        context_store.delete(session_id)
                        return
                    current_agent = new_agent
                    current_agent_path = cls._find_agent_path(agent, current_agent)
                    handoff_switched = True
                    break
            turn += 1
            if handoff_switched:
                continue
        yield Event(agent=getattr(current_agent, "name", "runner"), type=EventType.ERROR, data=f"超过最大轮次 {max_turns}")
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
        suspension_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> AsyncGenerator[Event, None]:
        """恢复执行被挂起的 Agent 会话"""
        ctx = context_store.load(session_id, shared_context_cls)
        if not ctx:
            yield Event(agent=agent.name, type=EventType.ERROR, data=f"找不到会话 {session_id} 的上下文快照")
            return

        if idempotency_key:
            existing = ctx.resume_idempotency.get(idempotency_key)
            if existing is not None:
                yield Event(
                    agent=agent.name,
                    type=EventType.HUMAN_INPUT_RECEIVED,
                    data={
                        "status": "duplicate_ignored",
                        "idempotency_key": idempotency_key,
                        "suspension_id": existing.get("suspension_id"),
                        "input": existing.get("user_input"),
                    },
                )
                return

        checkpoint = ctx.state.get("__runner_checkpoint__", {})
        max_turns = int(checkpoint.get("max_turns", 10))
        turn = int(checkpoint.get("turn", 0))
        path = checkpoint.get("agent_path") or []
        current_agent = cls._find_agent_by_path(agent, path) if path else None
        if current_agent is None:
            current_agent = cls._find_agent(agent, checkpoint.get("current_agent", "")) or agent
        current_agent_path = cls._find_agent_path(agent, current_agent)
        handoff_agent_cache: dict[str, Any | None] = {}

        pending = ctx.get_pending_suspension(suspension_id=suspension_id)
        if not pending:
            yield Event(
                agent=agent.name,
                type=EventType.ERROR,
                data=f"未找到可恢复的挂起点: {suspension_id or 'latest'}",
            )
            return
        resolved = ctx.resolve_suspension(pending.suspension_id, str(user_input))
        if resolved is None:
            yield Event(agent=agent.name, type=EventType.ERROR, data=f"挂起点不可恢复: {pending.suspension_id}")
            return

        if idempotency_key:
            ctx.resume_idempotency[idempotency_key] = {
                "suspension_id": resolved.suspension_id,
                "user_input": str(user_input),
            }

        yield Event(
            agent=agent.name,
            type=EventType.HUMAN_INPUT_RECEIVED,
            data={
                "input": user_input,
                "suspension_id": resolved.suspension_id,
                "tool": resolved.tool_name,
                "tool_call_id": resolved.tool_call_id,
            },
        )

        if resolved.resume_strategy == "as_tool_result":
            ctx.add_tool_result(resolved.tool_call_id, str(user_input))
        else:
            yield Event(
                agent=agent.name,
                type=EventType.ERROR,
                data=f"不支持的恢复策略: {resolved.resume_strategy}",
            )
            return

        while turn < max_turns:
            ctx.state["__runner_checkpoint__"] = {
                "turn": turn,
                "max_turns": max_turns,
                "current_agent": getattr(current_agent, "name", ""),
                "agent_path": current_agent_path,
            }
            handoff_switched = False
            async for event in current_agent.run(ctx):
                if event.type == EventType.SUSPEND_REQUESTED:
                    suspension_id = cls._ensure_suspension_record(ctx, current_agent, event)
                    yield event
                    context_store.save(session_id, ctx)
                    yield Event(
                        agent=getattr(current_agent, "name", "runner"),
                        type="suspended",
                        data={
                            "session_id": session_id,
                            "turn": turn,
                            "current_agent": getattr(current_agent, "name", ""),
                            "agent_path": current_agent_path,
                            "suspension_id": suspension_id,
                        },
                    )
                    return
                yield event
                if event.type == EventType.FINAL_OUTPUT:
                    context_store.delete(session_id)
                    return
                if event.type == EventType.ERROR:
                    context_store.delete(session_id)
                    return
                if event.type == EventType.HANDOFF:
                    target_name = ""
                    if isinstance(event.data, dict):
                        target_name = event.data.get("target", "")
                    if target_name in handoff_agent_cache:
                        new_agent = handoff_agent_cache[target_name]
                    else:
                        new_agent = cls._find_agent(agent, target_name)
                        handoff_agent_cache[target_name] = new_agent
                    if not new_agent:
                        yield Event(agent=getattr(current_agent, "name", "runner"), type=EventType.ERROR, data=f"Handoff 目标 '{target_name}' 未找到")
                        context_store.delete(session_id)
                        return
                    current_agent = new_agent
                    current_agent_path = cls._find_agent_path(agent, current_agent)
                    handoff_switched = True
                    break
            turn += 1
            if handoff_switched:
                continue
        yield Event(agent=getattr(current_agent, "name", "runner"), type=EventType.ERROR, data=f"超过最大轮次 {max_turns}")
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

    @staticmethod
    def _find_agent_path(root: Any, target: Any) -> list[str]:
        if root is target:
            return [getattr(root, "name", "")]
        if hasattr(root, "sub_agents"):
            for sub in root.sub_agents:
                sub_path = Runner._find_agent_path(sub, target)
                if sub_path:
                    return [getattr(root, "name", "")] + sub_path
        if hasattr(root, "handoffs"):
            for h in root.handoffs:
                if h is target:
                    return [getattr(root, "name", ""), getattr(h, "name", "")]
        return []

    @staticmethod
    def _find_agent_by_path(root: Any, path: list[str]) -> Any | None:
        if not path:
            return None
        if getattr(root, "name", None) != path[0]:
            return None
        node = root
        for part in path[1:]:
            next_node = None
            if hasattr(node, "sub_agents"):
                for sub in node.sub_agents:
                    if getattr(sub, "name", None) == part:
                        next_node = sub
                        break
            if next_node is None and hasattr(node, "handoffs"):
                for h in node.handoffs:
                    if getattr(h, "name", None) == part:
                        next_node = h
                        break
            if next_node is None:
                return None
            node = next_node
        return node

    @staticmethod
    def _ensure_suspension_record(ctx: RunContext, current_agent: Any, event: Event) -> str:
        data = event.data if isinstance(event.data, dict) else {}
        existing_id = data.get("suspension_id")
        if existing_id:
            return existing_id
        record = ctx.register_suspension(
            tool_call_id=data.get("tool_call_id") or f"manual-{getattr(current_agent, 'name', 'agent')}",
            tool_name=data.get("tool") or "manual_input",
            prompt=data.get("prompt") or "需要人工输入",
            form_schema=data.get("form_schema"),
            resume_strategy=data.get("resume_strategy", "as_tool_result"),
        )
        if isinstance(event.data, dict):
            event.data["suspension_id"] = record.suspension_id
            event.data.setdefault("tool_call_id", record.tool_call_id)
            event.data.setdefault("tool", record.tool_name)
            event.data.setdefault("resume_strategy", record.resume_strategy)
        return record.suspension_id
