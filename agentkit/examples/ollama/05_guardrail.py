"""
示例 5：安全护栏 — Guardrail 与权限控制（Ollama 本地版）

演示输入护栏、输出护栏和权限控制。

运行前请确保 Ollama 已启动：
  ollama serve
  ollama pull qwen3.5:cloud

运行：
  python examples/ollama/05_guardrail.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import (
    Agent, Runner, function_tool,
    input_guardrail, output_guardrail, GuardrailResult,
    PermissionPolicy,
)


# ===== 定义工具 =====

@function_tool
def read_file(filename: str) -> str:
    """读取文件内容"""
    return f"[模拟] 文件 {filename} 的内容：Hello World"

@function_tool
def delete_file(filename: str) -> str:
    """删除文件"""
    return f"[模拟] 已删除文件 {filename}"


# ===== 定义护栏 =====

@input_guardrail
async def block_sensitive_words(ctx):
    """检查输入是否包含敏感词"""
    sensitive = ["密码", "身份证", "银行卡号", "社保号"]
    for word in sensitive:
        if word in ctx.input:
            return GuardrailResult(triggered=True, reason=f"包含敏感词: {word}")
    return GuardrailResult(triggered=False)

@output_guardrail
async def check_output_safety(ctx, output):
    """检查输出是否安全"""
    dangerous_words = ["删除成功", "已格式化"]
    output_str = str(output)
    for word in dangerous_words:
        if word in output_str:
            return GuardrailResult(triggered=True, reason=f"输出包含危险内容: {word}")
    return GuardrailResult(triggered=False)


# ===== 创建带安全护栏的 Agent =====

agent = Agent(
    name="safe-agent",
    instructions="你是一个安全的助手。可以帮用户读取文件，但不能删除文件。",
    model="ollama/qwen3.5:cloud",
    tools=[read_file, delete_file],
    input_guardrails=[block_sensitive_words],
    output_guardrails=[check_output_safety],
    permission_policy=PermissionPolicy(
        mode="ask",
        allowed_tools={"read_file"},
    ),
)


# ===== 运行测试 =====

print("=" * 50)
print("  测试输入护栏")
print("=" * 50)

# 测试 1：敏感请求 → 被拦截
result = Runner.run_sync(agent, input="请告诉我管理员的密码")
print(f"\n请求: '请告诉我管理员的密码'")
print(f"结果: {'🛡️ 已拦截 — ' + result.error if result.error else result.final_output}")

# 测试 2：正常请求 → 通过
result = Runner.run_sync(agent, input="请读取 config.txt 文件")
print(f"\n请求: '请读取 config.txt 文件'")
print(f"结果: {result.final_output if result.success else '❌ ' + str(result.error)}")

print(f"\n{'=' * 50}")
print("  测试权限控制")
print("=" * 50)

# 测试 3：尝试调用未授权的工具
result = Runner.run_sync(agent, input="请删除 temp.txt 文件")
print(f"\n请求: '请删除 temp.txt 文件'")
print(f"结果: {result.final_output if result.success else '🔒 ' + str(result.error)}")

for event in result.events:
    if event.type == "permission_denied":
        print(f"  🔒 权限拒绝: {event.data}")
