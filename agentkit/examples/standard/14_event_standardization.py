"""
示例 14：事件协议标准化与强类型校验

演示 EventType 枚举的使用，以及如何通过 Pydantic 对 Event data 进行强类型校验。
"""
import asyncio
from agentkit import Agent, Runner
from agentkit.runner.events import EventType
from pydantic import BaseModel

# 定义强类型的事件数据 Schema
class ToolResultSchema(BaseModel):
    tool: str
    result: str

async def main():
    print("=== 事件协议标准化与强类型校验示例 ===")
    
    agent = Agent(
        name="math_agent",
        instructions="你是一个计算助手。计算 10 + 20 的结果。",
        model="gpt-4o-mini"
    )
    
    print("\n[运行 Agent 并监听标准事件]")
    async for event in Runner.run_streamed(agent, input="开始计算"):
        # 1. 使用标准 EventType 进行匹配
        if event.type == EventType.LLM_RESPONSE:
            print(f"[{event.type.value}] LLM 返回了响应")
            
        elif event.type == EventType.TOOL_CALL:
            print(f"[{event.type.value}] 准备调用工具: {event.data.get('tool')}")
            
        elif event.type == EventType.TOOL_RESULT:
            # 2. 使用 validate_data 进行强类型校验
            try:
                # 校验 event.data 是否符合 ToolResultSchema 结构
                validated_data = event.validate_data(ToolResultSchema)
                print(f"[{event.type.value}] 工具校验成功 -> 工具名: {validated_data.tool}, 结果: {validated_data.result}")
            except ValueError as e:
                print(f"[{event.type.value}] 工具结果校验失败: {e}")
                
        elif event.type == EventType.FINAL_OUTPUT:
            print(f"\n[{event.type.value}] 最终结果: {event.data}")
            
        elif event.type == EventType.ERROR:
            print(f"[{event.type.value}] 发生错误: {event.data}")

if __name__ == "__main__":
    asyncio.run(main())
