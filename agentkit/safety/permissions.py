"""
agentkit/safety/permissions.py — 权限控制策略
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Optional


class PermissionPolicy:
    """
    工具权限控制策略。
    三种粒度：预设模式 → 白名单 → 自定义回调
    """

    def __init__(
        self,
        mode: str = "ask",
        allowed_tools: set[str] | None = None,
        custom_check: Callable | None = None,
    ):
        self.mode = mode                         # "allow_all" / "deny_all" / "ask"
        self.allowed_tools = allowed_tools or set()
        self.custom_check = custom_check

    async def check(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        if self.mode == "allow_all":
            return True
        if self.mode == "deny_all":
            return False

        if tool_name in self.allowed_tools:
            return True

        if self.custom_check:
            result = self.custom_check(tool_name, arguments)
            if inspect.isawaitable(result):
                result = await result
            return bool(result)

        return False
