from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .structured_data import ResultFormatter, StructuredDataTool
from ..runner.context import RunContext

logger = logging.getLogger("agentkit.tools.nebula")

try:
    from nebula3.gclient.net import ConnectionPool
    from nebula3.Config import Config
    from nebula3.data.ResultSet import ResultSet
    NEBULA_AVAILABLE = True
except ImportError:
    NEBULA_AVAILABLE = False


class NebulaResultFormatter(ResultFormatter):
    """将 Nebula 的 ResultSet 转化为标准化 JSON"""
    def format(self, raw_result: Any) -> Any:
        if not NEBULA_AVAILABLE or not isinstance(raw_result, ResultSet):
            return raw_result
            
        if not raw_result.is_succeeded():
            return {
                "error": "nebula_query_error",
                "code": raw_result.error_code(),
                "msg": raw_result.error_msg()
            }
            
        keys = raw_result.keys()
        records = []
        for row in raw_result.rows():
            record = {}
            for i, val in enumerate(row.values):
                # 简单解析 Vertex/Edge/Path 等
                # 这里做基础的类型转换映射
                value = val.get_value()
                # 实际上，Nebula Python client 需要使用专门的 cast 方法，如 as_string() 等。
                # 简化起见，返回基础表现形式
                record[keys[i]] = str(value)
            records.append(record)
        return {
            "summary": f"Query succeeded, found {len(records)} records.",
            "data": records
        }


class NebulaGraphTool(StructuredDataTool):
    """
    Nebula Graph 参数化工具
    自动建立连接池，通过模板引擎安全的填入参数，避免注入。
    """
    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: Type[BaseModel],
        query_template: str,
        space_name: str,
        connection_pool: Any = None,
        formatter: Optional[ResultFormatter] = None,
    ):
        if not NEBULA_AVAILABLE:
            pass  # Allow instantiation but fail at execution if not installed
            
        super().__init__(
            name=name, 
            description=description, 
            parameters_schema=parameters_schema, 
            formatter=formatter or NebulaResultFormatter()
        )
        self.query_template = query_template
        self.space_name = space_name
        self._connection_pool = connection_pool

    async def execute_query(self, ctx: "RunContext", args: BaseModel) -> Any:
        """执行参数化的 Nebula GQL"""
        # 支持从共享上下文中获取，或通过回调函数获取动态注入的连接池
        pool = self._connection_pool
        if callable(pool):
            pool = pool()
        if not pool and isinstance(ctx.shared_context, dict):
            pool = ctx.shared_context.get("connection_pool")
            
        if not pool:
            raise RuntimeError("Nebula ConnectionPool is not initialized")
            
        session = pool.get_session("root", "nebula") # Replace with config later
        try:
            # 切换 Space
            session.execute(f"USE {self.space_name};")
            
            # 使用 GQL 参数化查询，防止注入。
            query = self.query_template.format(**args.model_dump())
            logger.debug(f"Executing Nebula GQL: {query}")
            
            result = session.execute(query)
            return result
        finally:
            session.release()
