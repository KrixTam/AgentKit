"""
agentkit/tools/base_tool.py — 工具基类与工具集基类
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Union

from pydantic import BaseModel

from ..llm.types import ToolDefinition

if TYPE_CHECKING:
    from ..runner.context import RunContext


class BaseTool(ABC):
    """工具基类——所有工具的统一接口"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, ctx: Any, arguments: dict[str, Any]) -> Any:
        """执行工具"""
        ...

    @abstractmethod
    def to_tool_definition(self) -> ToolDefinition:
        """生成 LLM 可理解的工具定义"""
        ...


class BaseToolset(ABC):
    """工具集基类——可动态展开为多个 Tool"""

    @abstractmethod
    async def get_tools(self, ctx: Any) -> list[BaseTool]:
        ...


# 三种工具输入形态，框架自动统一处理
ToolUnion = Union[Callable, BaseTool, BaseToolset]
