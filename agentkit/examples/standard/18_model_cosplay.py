"""
示例 18：ModelCosplay（标准版）

目标：
1. 默认关闭 ModelCosplay 时，不允许在实例化时覆盖预设 model。
2. 开启 ModelCosplay 后，允许实例化时覆盖预设 model。
3. 开启 ModelCosplay 后，允许运行时通过 apply_model_cosplay 切换 model。

说明：
- 本示例不调用真实 LLM，仅输出当前 Agent 使用的 model，便于本地快速验证能力开关逻辑。
- 运行：
    python examples/standard/18_model_cosplay.py
"""
from __future__ import annotations

import os
import sys
from typing import AsyncGenerator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentkit import Agent, Runner
from agentkit.runner.events import Event, EventType


class ModelEchoAgent(Agent):
    async def _run_impl(self, ctx) -> AsyncGenerator[Event, None]:
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=f"active_model={self.model}")


class LockedStandardAgent(ModelEchoAgent):
    model: str = "gpt-4o-mini"
    model_cosplay_enabled: bool = False


class CosplayStandardAgent(ModelEchoAgent):
    model: str = "gpt-4o-mini"
    model_cosplay_enabled: bool = True


def main() -> None:
    print("=== 1) 关闭能力：实例化覆盖应失败 ===")
    try:
        LockedStandardAgent(name="locked-agent", model="gpt-4o")
        print("❌ 预期失败，但实例化成功了")
    except ValueError as e:
        print(f"✅ 拒绝覆盖成功: {e}")

    print("\n=== 2) 开启能力：实例化覆盖应成功 ===")
    cosplay_agent = CosplayStandardAgent(name="cosplay-agent", model="gpt-4o")
    result = Runner.run_sync(cosplay_agent, input="show model")
    print(f"✅ 实例化覆盖后输出: {result.final_output}")

    print("\n=== 3) 开启能力：运行时覆盖应成功 ===")
    runtime_agent = CosplayStandardAgent(name="runtime-agent")
    runtime_agent.apply_model_cosplay("gpt-4o")
    result = Runner.run_sync(runtime_agent, input="show model")
    print(f"✅ 运行时覆盖后输出: {result.final_output}")


if __name__ == "__main__":
    main()
