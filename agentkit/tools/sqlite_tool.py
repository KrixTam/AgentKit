from __future__ import annotations

import logging
import sqlite3
from typing import Any, Optional, Type

from pydantic import BaseModel

from .structured_data import ResultFormatter, StructuredDataTool
from ..runner.context import RunContext

logger = logging.getLogger("agentkit.tools.sqlite")


class SQLiteResultFormatter(ResultFormatter):
    """将 SQLite 的字典行列表转化为标准化 JSON"""
    def format(self, raw_result: Any) -> Any:
        if not isinstance(raw_result, list):
            return raw_result
        return {
            "summary": f"Query succeeded, found {len(raw_result)} records.",
            "data": raw_result
        }


class SQLiteTool(StructuredDataTool):
    """
    SQLite 参数化工具
    通过 sqlite3 自带的占位符机制执行参数化查询，彻底避免 SQL 注入。
    """
    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: Type[BaseModel],
        query_template: str,
        db_path: str = ":memory:",
        formatter: Optional[ResultFormatter] = None,
    ):
        super().__init__(
            name=name, 
            description=description, 
            parameters_schema=parameters_schema, 
            formatter=formatter or SQLiteResultFormatter()
        )
        self.query_template = query_template
        self.db_path = db_path

    async def execute_query(self, ctx: "RunContext", args: BaseModel) -> Any:
        """执行参数化的 SQL"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            # 使用 sqlite3 内置的字典命名占位符机制执行查询，这是 100% 安全的防注入方式
            # args.model_dump() 提供由 Pydantic 严格校验过的字典
            logger.debug(f"Executing SQLite query: {self.query_template} with params {args.model_dump()}")
            
            cursor.execute(self.query_template, args.model_dump())
            conn.commit()
            
            # 如果是查询语句，返回结果；如果是插入/更新，fetchall 会为空
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error: {e}")
        finally:
            cursor.close()
            conn.close()
