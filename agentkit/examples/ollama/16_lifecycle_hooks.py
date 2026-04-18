"""
16_lifecycle_hooks.py — 生命周期 Hooks 与 Callbacks (Ollama 版)

本示例展示了：
1. Agent 级别的 before_agent_callback 和 after_agent_callback
2. 细粒度的 Hook 拦截点：before_model, after_model, before_tool, after_tool, before_handoff, after_handoff, on_error
3. 同步/异步回调支持
4. 请求与响应的改写（例如：在 before_model 中改写 instructions，在 after_model 中改写输出）
5. 异常的降级处理与耗时监控
"""
import sys
import os
import asyncio
import logging

# 确保能导入 agentkit
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from agentkit.agents.agent import Agent
from agentkit.runner.runner import Runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")

# === 回调函数定义 ===
async def before_agent(ctx):
    logging.info(f"==> [Hook] before_agent: 收到请求 input='{ctx.input}'")

async def after_agent(ctx):
    logging.info(f"==> [Hook] after_agent: 运行结束")

async def before_model(ctx, instructions, tools):
    logging.info("==> [Hook] before_model: 准备调用 LLM，改写 Prompt 加入时间信息")
    
async def after_model(ctx, response):
    logging.info(f"==> [Hook] after_model: 收到 LLM 响应内容长度 {len(response.content) if response.content else 0}")
    # 改写响应：给 LLM 的输出增加免责声明
    if response.content:
        response.content += "\n\n[安全审计系统: 本回答由 AI 生成]"
    return response

def before_tool(ctx, tool, tool_call):
    logging.info(f"==> [Hook] before_tool: 准备执行工具 {tool.name} 参数: {tool_call.arguments}")

async def after_tool(ctx, tool, result):
    logging.info(f"==> [Hook] after_tool: 工具 {tool.name} 执行完成，结果: {result}")
    return result

def on_error(ctx, error):
    logging.error(f"==> [Hook] on_error: 捕获到异常 {error}")

# === 定义工具 ===
def get_weather(location: str) -> str:
    """获取天气信息"""
    if "Error" in location:
        raise ValueError("模拟天气服务异常")
    return f"{location} 今天晴天，25度"

async def main():
    agent = Agent(
        name="HookAgent",
        instructions="你是一个天气助手。请使用工具查询天气。",
        tools=[get_weather],
        model="ollama/qwen2.5:7b", # Ollama
        
        # 注册回调
        before_agent_callback=before_agent,
        after_agent_callback=after_agent,
        before_model_callback=before_model,
        after_model_callback=after_model,
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
        on_error_callback=on_error,
        
        # hook 异常降级不中断流程
        fail_fast_on_hook_error=False,
    )

    print("\n--- 正常流程测试 ---")
    result = await Runner.run(agent, input="北京天气如何？")
    print(f"\nFinal Output:\n{result.final_output}")
    
    print("\n--- 异常捕获测试 ---")
    async def bad_hook(ctx, response):
        raise RuntimeError("Hook 内部发生了严重错误！")
        
    agent.after_model_callback = bad_hook
    result2 = await Runner.run(agent, input="上海天气如何？")
    
    print(f"\n可以看到，由于 fail_fast_on_hook_error=False，Hook 的异常只是被作为 Event 抛出并记录，没有中断主流程。")
    # 查找 error event
    for event in result2.events:
        if event.type == "error":
            print(f"捕获到的错误事件: {event.data}")
            
if __name__ == "__main__":
    asyncio.run(main())