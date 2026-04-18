"""
示例 12：RunContext 序列化与共享状态

演示如何序列化和反序列化 RunContext，以及如何处理自定义的 shared_context。
"""
import asyncio
from agentkit.runner.context import RunContext

# 自定义共享状态，实现序列化协议
class MySharedState:
    def __init__(self, user_role: str, access_level: int):
        self.user_role = user_role
        self.access_level = access_level

    def __ak_serialize__(self) -> dict:
        return {
            "user_role": self.user_role,
            "access_level": self.access_level
        }

    @classmethod
    def __ak_deserialize__(cls, data: dict) -> "MySharedState":
        return cls(
            user_role=data.get("user_role", "guest"),
            access_level=data.get("access_level", 0)
        )

async def main():
    print("=== RunContext 序列化与反序列化示例 ===")
    
    # 1. 创建带有初始状态和 shared_context 的 RunContext
    original_ctx = RunContext(
        input="你好，我是管理员",
        shared_context=MySharedState(user_role="admin", access_level=9),
        user_id="user_123"
    )
    original_ctx.state["turn_count"] = 1
    original_ctx.add_message("user", "你好，我是管理员")
    original_ctx.add_message("assistant", "您好，管理员！")
    
    # 2. 序列化为 JSON 字符串
    json_data = original_ctx.to_json()
    print("\n[序列化后的 JSON 数据]:")
    print(json_data)
    
    # 3. 从 JSON 字符串反序列化，并恢复 shared_context
    restored_ctx = RunContext.from_json(json_data, shared_context_cls=MySharedState)
    
    print("\n[反序列化后的上下文]:")
    print(f"Session ID: {restored_ctx.session_id}")
    print(f"User ID: {restored_ctx.user_id}")
    print(f"State: {restored_ctx.state}")
    print(f"Shared Context - Role: {restored_ctx.shared_context.user_role}, Level: {restored_ctx.shared_context.access_level}")
    print(f"Messages count: {len(restored_ctx.messages)}")

if __name__ == "__main__":
    asyncio.run(main())
