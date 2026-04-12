"""
agentkit/safety/guardrails.py — 安全护栏（Input / Output）
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class GuardrailResult:
    """护栏检查结果"""
    triggered: bool = False
    reason: Optional[str] = None
    info: dict[str, Any] = field(default_factory=dict)


class InputGuardrail:
    """输入安全护栏"""

    def __init__(self, check_fn: Callable, *, name: str | None = None, parallel: bool = True):
        self.check_fn = check_fn
        self.name = name or getattr(check_fn, "__name__", "input_guardrail")
        self.parallel = parallel

    async def check(self, ctx: Any) -> GuardrailResult:
        result = self.check_fn(ctx)
        if inspect.isawaitable(result):
            result = await result
        return result


class OutputGuardrail:
    """输出安全护栏"""

    def __init__(self, check_fn: Callable, *, name: str | None = None):
        self.check_fn = check_fn
        self.name = name or getattr(check_fn, "__name__", "output_guardrail")

    async def check(self, ctx: Any, output: Any) -> GuardrailResult:
        result = self.check_fn(ctx, output)
        if inspect.isawaitable(result):
            result = await result
        return result


def input_guardrail(fn: Callable) -> InputGuardrail:
    """装饰器"""
    return InputGuardrail(fn)


def output_guardrail(fn: Callable) -> OutputGuardrail:
    """装饰器"""
    return OutputGuardrail(fn)
