from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from pydantic import BaseModel

from .base_tool import BaseTool
from ..llm.types import ToolDefinition
from ..runner.context import RunContext

logger = logging.getLogger("agentkit.tools.structured")

class ResultFormatter(ABC):
    """结果格式化协议"""
    @abstractmethod
    def format(self, raw_result: Any) -> Any:
        pass


class StructuredDataTool(BaseTool, ABC):
    """
    结构化数据源参数化 Tool 基类
    采用“模板 + 参数”模式，LLM 仅输出结构化参数，底层查询由 Tool 内部拼装并执行。
    避免 LLM 直接拼接查询语句带来的安全风险。
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: Type[BaseModel],
        formatter: Optional[ResultFormatter] = None,
    ):
        self._name = name
        self._description = description
        self._parameters_schema = parameters_schema
        self._formatter = formatter

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def to_tool_definition(self) -> ToolDefinition:
        schema = self._parameters_schema.model_json_schema()
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=schema,
        )

    async def execute(self, ctx: "RunContext", arguments: dict[str, Any]) -> Any:
        """执行查询"""
        try:
            # 参数校验：类型、范围、必填等（通过 Pydantic 自动完成）
            validated_args = self._parameters_schema.model_validate(arguments)
        except Exception as e:
            return {"error": "parameter_validation_failed", "details": str(e)}

        try:
            # 模板拼接与执行（安全策略：禁止直接拼接，使用参数化查询）
            raw_result = await self.execute_query(ctx, validated_args)
        except Exception as e:
            return self.handle_query_error(e)

        # 输出策略：默认输出规范化 JSON
        if self._formatter:
            try:
                return self._formatter.format(raw_result)
            except Exception as e:
                return {"error": "formatting_failed", "details": str(e)}
        return raw_result

    @abstractmethod
    async def execute_query(self, ctx: "RunContext", args: BaseModel) -> Any:
        """执行底层查询逻辑（必须实现为参数化查询）"""
        pass

    def handle_query_error(self, e: Exception) -> dict[str, Any]:
        """错误语义：分类连接失败、查询失败、权限失败等"""
        error_str = str(e).lower()
        if "connection" in error_str or "timeout" in error_str:
            return {"error": "connection_failed", "details": str(e)}
        elif "permission" in error_str or "access denied" in error_str:
            return {"error": "permission_denied", "details": str(e)}
        else:
            return {"error": "query_failed", "details": str(e)}
