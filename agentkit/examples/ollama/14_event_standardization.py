"""
示例 14：事件协议标准化与强类型校验（Ollama 版）

演示 EventType 枚举的使用，以及如何通过 Pydantic 对 Event data 进行强类型校验。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import asyncio
from agentkit import Agent, Runner
from agentkit.runner.events import EventType
from pydantic import BaseModel

# 定义强类型的事件数据 Schema
class ToolResultSchema(BaseModel):
    tool: str
    result: str

class FinalOutputSchema(BaseModel):
    # 对于 Final Output，底层直接传入字符串，为了演示这里使用 Pydantic 包装
    # 但实际的 FINAL_OUTPUT event.data 是字符串
    pass

async def main():
    print("=== 事件协议标准化与强类型校验示例 ===")
    
    agent = Agent(
        name="math_agent",
        instructions="你是一个计算助手。计算 10 + 20 的结果。",
        model="ollama/qwen3.5:cloud"
    )
    
    print("\n[运行 Agent 并监听标准事件]")
    async for event in Runner.run_streamed(agent, input="开始计算"):
        event_type = event.type.value if hasattr(event.type, "value") else str(event.type)

        # 1. 使用标准 EventType 进行匹配
        if event.type == EventType.LLM_RESPONSE:
            print(f"[{event_type}] LLM 返回了响应")
            
        elif event.type == EventType.TOOL_CALL:
            print(f"[{event_type}] 准备调用工具: {event.data.get('tool')}")
            
        elif event.type == EventType.TOOL_RESULT:
            # 2. 使用 validate_data 进行强类型校验
            try:
                # 校验 event.data 是否符合 ToolResultSchema 结构
                validated_data = event.validate_data(ToolResultSchema)
                print(f"[{event_type}] 工具校验成功 -> 工具名: {validated_data.tool}, 结果: {validated_data.result}")
            except ValueError as e:
                print(f"[{event_type}] 工具结果校验失败: {e}")
                
        elif event.type == EventType.FINAL_OUTPUT:
            print(f"\n[{event_type}] 最终结果: {event.data}")
            
        elif event.type == EventType.ERROR:
            print(f"[{event_type}] 发生错误: {event.data}")

if __name__ == "__main__":
    asyncio.run(main())
