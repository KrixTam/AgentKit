"""
示例 5（Playground/HITL 专用）：Human-in-the-loop Agent（Ollama 版）

用途：
- 提供一个可被 AgentHub `entry` 直接加载的 `agent` 实例；
- 在工具执行前通过 `request_human_input(...)` 触发挂起，便于在 Playground 中演示 HITL。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent
from agentkit.tools.base_tool import request_human_input
from agentkit.tools.function_tool import FunctionTool


def confirm_action(action: str) -> str:
    """敏感操作执行前请求人工确认。"""
    request_human_input(f"即将执行敏感操作: {action}，请确认 (approve/reject)")


def execute_action(action: str) -> str:
    """执行操作（示例返回）。"""
    return f"操作 '{action}' 已执行。"


confirm_tool = FunctionTool.from_function(confirm_action)
execute_tool = FunctionTool.from_function(execute_action)


agent = Agent(
    name="hitl-agent",
    instructions=(
        "你是一个需要人工审批的运维助手。"
        "当用户要求执行敏感操作时，必须先调用 confirm_action 请求人工确认；"
        "收到确认后再调用 execute_action。"
    ),
    # 使用纯本地模型，避免 cloud 变体在未鉴权/网络抖动时触发远端 502。
    model="ollama/qwen3.5:4b",
    tools=[confirm_tool, execute_tool],
)
