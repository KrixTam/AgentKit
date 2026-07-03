"""
示例：三种运行方式对比 — 同步 / 异步 / 流式（标准版）

演示 Agent 的三种运行方式在同一个 Agent 上的用法差异。

运行前请设置环境变量：
  export OPENAI_API_KEY="sk-..."

运行：
  python examples/standard/07_sync_async_stream.py
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from model_config import resolve_model

from agentkit import Agent, function_tool

# ===== 定义一个简单工具 =====

@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return {"北京": "晴，25°C", "上海": "多云，22°C"}.get(city, f"{city}：暂无数据")

# ===== 创建 Agent =====

agent = Agent(
    name="assistant",
    instructions="你是一个简洁的中文助手。回答尽量简短。",
    model=resolve_model("gpt-4o"),
    tools=[get_weather],
)

# ============================================================
# 方式 1：同步运行 — agent.invoke()
# ============================================================

def demo_sync():
    print("=" * 50)
    print("  方式 1：同步运行 — agent.invoke()")
    print("=" * 50)

    start = time.time()
    result = agent.invoke(input="北京今天天气如何？")
    elapsed = time.time() - start

    if result.success:
        print(f"  ✅ 回复: {result.final_output}")
    else:
        print(f"  ❌ 错误: {result.error}")
    print(f"  ⏱️ 耗时: {elapsed:.1f}s")

# ============================================================
# 方式 2：异步运行 — await agent.ainvoke()
# ============================================================

async def demo_async():
    print(f"\n{'=' * 50}")
    print("  方式 2：异步运行 — await agent.ainvoke()")
    print("=" * 50)

    start = time.time()
    result = await agent.ainvoke(input="上海今天天气如何？")
    elapsed = time.time() - start

    if result.success:
        print(f"  ✅ 回复: {result.final_output}")
    else:
        print(f"  ❌ 错误: {result.error}")
    print(f"  ⏱️ 耗时: {elapsed:.1f}s")

# ============================================================
# 方式 2b：异步并发 — 同时运行多个 Agent
# ============================================================

async def demo_async_concurrent():
    print(f"\n{'=' * 50}")
    print("  方式 2b：异步并发 — 同时运行多个请求")
    print("=" * 50)

    queries = [
        "1+1等于几？只回答数字",
        "北京今天天气如何？",
        "用一句话解释什么是 Python",
    ]

    start = time.time()
    results = await asyncio.gather(*[
        agent.ainvoke(input=q) for q in queries
    ])
    elapsed = time.time() - start

    for q, r in zip(queries, results):
        status = f"✅ {r.final_output}" if r.success else f"❌ {r.error}"
        print(f"  [{q[:15]:15s}] → {status}")

    print(f"  ⏱️ 3 个请求并发总耗时: {elapsed:.1f}s")

# ============================================================
# 方式 3：流式运行 — agent.stream()
# ============================================================

async def demo_stream():
    print(f"\n{'=' * 50}")
    print("  方式 3：流式运行 — agent.stream()")
    print("=" * 50)

    print("  📡 实时事件流:")

    start = time.time()
    async for event in agent.stream(input="北京今天天气如何？"):
        elapsed = time.time() - start
        if event.type == "llm_response":
            has_tools = "有工具调用" if event.data.has_tool_calls else "纯文本"
            print(f"  [{elapsed:5.1f}s] 🤖 LLM 响应 ({has_tools})")
        elif event.type == "tool_result":
            tool_name = event.data.get("tool", "?")
            tool_result = event.data.get("result", "")
            print(f"  [{elapsed:5.1f}s] 🔧 工具 {tool_name} → {tool_result}")
        elif event.type == "final_output":
            print(f"  [{elapsed:5.1f}s] ✅ 最终输出: {event.data}")
        else:
            print(f"  [{elapsed:5.1f}s] 📋 {event.type}: {str(event.data)[:60]}")

# ============================================================
# 主入口
# ============================================================

def run_all():
    """先同步跑一个，再 asyncio.run 跑异步的"""

    print("🚀 AgentKit — 三种运行方式对比\n")

    # 方式 1：同步（必须在 asyncio.run 之外调用）
    demo_sync()

    # 方式 2、2b、3：异步
    async def async_demos():
        await demo_async()
        await demo_async_concurrent()
        await demo_stream()

    asyncio.run(async_demos())

    print(f"\n{'=' * 50}")
    print("  全部演示完成 🎉")
    print("=" * 50)
    print("""
📝 总结：
  invoke()        — 最简单，一行代码，适合脚本和测试
  await ainvoke() — 异步核心，可并发执行多个请求
  stream()        — 实时事件流，适合聊天 UI 和进度展示

⚠️ 注意：invoke() 内部调用 asyncio.run()，因此不能在
   已有事件循环中使用。如果你的代码已经是 async 的，
   请直接用 await agent.ainvoke()。
""")

if __name__ == "__main__":
    run_all()
