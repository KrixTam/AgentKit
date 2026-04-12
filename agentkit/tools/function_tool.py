"""
agentkit/tools/function_tool.py — FunctionTool + @function_tool 装饰器

一行代码把 Python 函数变成 LLM 可调用的工具。
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Optional

from ..llm.types import ToolDefinition
from ..utils.schema import FuncSchema, generate_function_schema
from .base_tool import BaseTool


class FunctionTool(BaseTool):
    """将 Python 函数包装为 LLM 可调用的工具"""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        handler: Callable,
        json_schema: dict[str, Any],
        takes_context: bool = False,
        needs_approval: bool = False,
        timeout_seconds: float | None = None,
    ):
        super().__init__(name=name, description=description)
        self._handler = handler
        self._json_schema = json_schema
        self._takes_context = takes_context
        self.needs_approval = needs_approval
        self.timeout_seconds = timeout_seconds

    async def execute(self, ctx: Any, arguments: dict[str, Any]) -> Any:
        if self._takes_context:
            result = self._handler(ctx, **arguments)
        else:
            result = self._handler(**arguments)

        if inspect.isawaitable(result):
            if self.timeout_seconds:
                result = await asyncio.wait_for(result, timeout=self.timeout_seconds)
            else:
                result = await result

        return result

    def to_tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self._json_schema,
        )

    @classmethod
    def from_function(cls, func: Callable, **kwargs: Any) -> "FunctionTool":
        """从普通 Python 函数创建 FunctionTool"""
        schema = generate_function_schema(func)
        return cls(
            name=schema.name,
            description=schema.description or "",
            handler=func,
            json_schema=schema.params_json_schema,
            takes_context=schema.takes_context,
            **kwargs,
        )


def function_tool(
    func: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    needs_approval: bool = False,
    timeout: float | None = None,
) -> FunctionTool | Callable:
    """
    装饰器：将 Python 函数自动转换为 FunctionTool。

    用法：
        @function_tool
        async def my_tool(query: str) -> str:
            '''工具描述'''
            ...

        @function_tool(needs_approval=True, timeout=30)
        async def dangerous_tool(target: str) -> str:
            ...
    """
    def decorator(fn: Callable) -> FunctionTool:
        schema = generate_function_schema(fn, name_override=name, desc_override=description)

        async def _invoke(ctx: Any = None, **kwargs: Any) -> Any:
            if schema.takes_context:
                result = fn(ctx, **kwargs)
            else:
                result = fn(**kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

        return FunctionTool(
            name=schema.name,
            description=schema.description or "",
            handler=_invoke,
            json_schema=schema.params_json_schema,
            takes_context=schema.takes_context,
            needs_approval=needs_approval,
            timeout_seconds=timeout,
        )

    if func is not None:
        return decorator(func)
    return decorator
