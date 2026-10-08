"""
示例 13：Human-in-the-loop 与断点续跑

演示如何通过 Runner checkpoint 保存挂起状态，并在人工输入后恢复执行。
为保证标准版批跑稳定，本示例使用确定性挂起逻辑，不依赖具体模型是否会先调用确认工具。
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from agentkit.agents.base_agent import BaseAgent
from agentkit.runner.context import RunContext
from agentkit import Runner
from agentkit.runner.context_store import InMemoryContextStore
from agentkit.runner.events import Event, EventType


class OpsApprovalAgent(BaseAgent):
    async def _run_impl(self, ctx: RunContext) -> AsyncGenerator[Event, None]:
        action = ctx.state.get("pending_action") or str(ctx.input)

        if not ctx.state.get("approval_requested"):
            ctx.state["approval_requested"] = True
            ctx.state["pending_action"] = action
            suspension = ctx.register_suspension(
                tool_call_id="manual-approval-1",
                tool_name="confirm_action",
                prompt=f"即将执行敏感操作: {action}，请确认 (yes/no)",
            )
            yield Event(
                agent=self.name,
                type=EventType.SUSPEND_REQUESTED,
                data={
                    "suspension_id": suspension.suspension_id,
                    "prompt": f"即将执行敏感操作: {action}，请确认 (yes/no)",
                    "tool": "confirm_action",
                    "tool_call_id": "manual-approval-1",
                },
            )
            return

        decision = "unknown"
        for msg in reversed(ctx.messages):
            if msg.get("role") == "tool" and msg.get("tool_call_id") == "manual-approval-1":
                decision = str(msg.get("content", "unknown")).strip().lower()
                break

        if decision in {"yes", "approve", "approved"}:
            result = f"操作 '{action}' 已成功执行！"
        else:
            result = f"操作 '{action}' 已取消执行。"

        yield Event(agent=self.name, type=EventType.TOOL_RESULT, data={"result": result})
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=result)

async def main():
    print("=== Human-in-the-loop 与断点续跑示例 ===")
    
    agent = OpsApprovalAgent(name="ops_agent")
    
    # 使用内存存储保存挂起的上下文
    store = InMemoryContextStore()
    session_id = "session_ops_001"
    
    print("\n[第 1 阶段：启动 Agent 并触发挂起]")
    user_input = "请帮我重启生产数据库"
    print(f"User: {user_input}")
    
    async for event in Runner.run_with_checkpoint(
        agent,
        input=user_input,
        session_id=session_id,
        context_store=store
    ):
        if event.type == EventType.SUSPEND_REQUESTED:
            print(f"\n>> 🚨 Agent 挂起！等待人工输入...")
            print(f">> 提示: {event.data.get('prompt')}")
            print(f">> 工具: {event.data.get('tool')}")
        elif event.type == EventType.TOOL_CALL:
            print(f"Agent 调用工具: {event.data.get('tool')}")
        elif event.type == EventType.LLM_RESPONSE:
            print("Agent 正在思考...")
            
    # 此时 Agent 已经结束运行并保存在了 store 中
    assert store.load(session_id) is not None
    print("\n[当前状态]: Agent 已被挂起，进程可以完全退出。")
    
    # 模拟人工介入
    await asyncio.sleep(1)
    print("\n[第 2 阶段：人工提供输入并恢复执行]")
    human_reply = "yes"
    print(f"Human: {human_reply}")
    
    async for event in Runner.resume(
        agent,
        session_id=session_id,
        user_input=human_reply,
        context_store=store
    ):
        if event.type == EventType.HUMAN_INPUT_RECEIVED:
            print(f"系统: 成功接收人工输入 '{event.data.get('input')}'")
        elif event.type == EventType.TOOL_RESULT:
            print(f"工具执行结果: {event.data.get('result')}")
        elif event.type == EventType.FINAL_OUTPUT:
            print(f"\nAgent 最终输出: {event.data}")
            
    # 恢复执行完毕后，状态会被清理
    assert store.load(session_id) is None
    print("\n[状态]: 执行完毕，会话清理完成。")

if __name__ == "__main__":
    asyncio.run(main())
