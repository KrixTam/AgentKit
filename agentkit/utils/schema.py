"""
agentkit/utils/schema.py — Python 函数签名 → JSON Schema 自动转换
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints

from pydantic import BaseModel, create_model


@dataclass
class FuncSchema:
    """解析后的函数 Schema"""
    name: str
    description: str | None
    params_pydantic_model: type[BaseModel]
    params_json_schema: dict[str, Any]
    takes_context: bool = False  # 第一个参数是否是上下文


def generate_function_schema(
    func: Callable,
    *,
    name_override: str | None = None,
    desc_override: str | None = None,
) -> FuncSchema:
    """从 Python 函数签名自动生成 JSON Schema"""
    name = name_override or func.__name__
    description = desc_override or (inspect.getdoc(func) or "").split("\n")[0]

    hints = get_type_hints(func)
    sig = inspect.signature(func)

    # 构建 Pydantic 模型的字段
    fields: dict[str, Any] = {}
    required: list[str] = []
    takes_context = False

    for i, (param_name, param) in enumerate(sig.parameters.items()):
        # 跳过 self / cls
        if param_name in ("self", "cls"):
            continue

        # 检查第一个参数是否是上下文类型
        if i == 0 and param_name in ("ctx", "context", "tool_context"):
            takes_context = True
            continue

        annotation = hints.get(param_name, str)
        # 跳过 return type
        if param_name == "return":
            continue

        if param.default is inspect.Parameter.empty:
            fields[param_name] = (annotation, ...)
            required.append(param_name)
        else:
            fields[param_name] = (annotation, param.default)

    # 创建动态 Pydantic 模型
    model_name = f"{name}_params"
    pydantic_model = create_model(model_name, **fields)
    json_schema = pydantic_model.model_json_schema()

    # 清理 schema 中的 title 等冗余字段
    _clean_schema(json_schema)

    return FuncSchema(
        name=name,
        description=description,
        params_pydantic_model=pydantic_model,
        params_json_schema=json_schema,
        takes_context=takes_context,
    )


def _clean_schema(schema: dict) -> None:
    """移除 Pydantic 生成的 schema 中的冗余字段"""
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
