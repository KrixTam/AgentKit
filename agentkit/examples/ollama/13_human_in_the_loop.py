"""
示例 13：Human-in-the-loop 与断点续跑（Ollama 版）

演示如何使用 request_human_input 请求人工介入，
并在挂起后通过 ContextStore 保存状态，之后再通过 resume 恢复执行。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import asyncio
from agentkit import Agent, Runner
from agentkit.tools.function_tool import FunctionTool
from agentkit.tools.base_tool import request_human_input
from agentkit.runner.context_store import InMemoryContextStore
from agentkit.runner.events import EventType

# 1. 定义一个需要人工介入的工具
def confirm_action(action: str) -> str:
    """在执行敏感操作前请求人工确认"""
    # 抛出中断异常，Runner 会将其转化为 suspend_requested 事件并挂起
    request_human_input(f"即将执行敏感操作: {action}，请确认 (yes/no)")

confirm_tool = FunctionTool.from_function(confirm_action)

# 2. 定义执行具体操作的工具
def execute_action(action: str) -> str:
    """执行操作"""
    return f"操作 '{action}' 已成功执行！"

execute_tool = FunctionTool.from_function(execute_action)

async def main():
    print("=== Human-in-the-loop 与断点续跑示例 ===")
    
    agent = Agent(
        name="ops_agent",
        instructions="你是一个运维助手。当用户要求执行操作时，你必须先使用 confirm_action 工具获取确认。只有确认后才能使用 execute_action 工具。",
        tools=[confirm_tool, execute_tool],
        model="ollama/qwen3.5:cloud" # 使用本地 Ollama 模型
    )
    
    # 使用内存存储保存挂起的上下文
    store = InMemoryContextStore()
    session_id = "session_ops_ollama_001"
    
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
