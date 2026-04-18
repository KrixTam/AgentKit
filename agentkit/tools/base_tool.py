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


class HumanInputRequested(Exception):
    """工具请求人工输入时抛出的异常"""
    def __init__(self, prompt: str, **kwargs):
        self.prompt = prompt
        self.kwargs = kwargs
        super().__init__(prompt)


def request_human_input(prompt: str, **kwargs: Any) -> Any:
    """
    Tool 层标准人工输入请求结果。
    抛出异常以中断当前执行，Runner 会捕获并挂起任务。
    """
    raise HumanInputRequested(prompt, **kwargs)


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
