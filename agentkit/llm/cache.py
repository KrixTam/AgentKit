"""
agentkit/llm/cache.py — LLM 响应缓存

对相同的 messages + tools 组合缓存 LLM 响应，避免重复调用。
使用内存 LRU 缓存，适合单进程场景。

用法:
    cache = LLMCache(max_size=128, ttl=300)
    result = cache.get(messages, tools)
    if result is None:
        result = await llm.generate(messages, tools=tools)
        cache.put(messages, tools, result)
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Optional

from .types import LLMResponse, Message, ToolDefinition


class LLMCache:
    """内存 LRU 缓存，支持 TTL 过期"""

    def __init__(self, max_size: int = 128, ttl: int = 300):
        """
        Args:
            max_size: 最大缓存条目数
            ttl: 缓存有效期（秒），0 表示永不过期
        """
        self._max_size = max_size
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[float, LLMResponse]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _make_key(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> str:
        """根据消息和工具列表生成缓存 key"""
        parts = []
        for msg in messages:
            parts.append(f"{msg.role.value}:{msg.content or ''}:{msg.tool_call_id or ''}")
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append(f"tc:{tc.name}:{json.dumps(tc.arguments, sort_keys=True)}")

        if tools:
            for tool in tools:
                parts.append(f"tool:{tool.name}:{json.dumps(tool.parameters, sort_keys=True)}")

        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> Optional[LLMResponse]:
        """查询缓存，命中返回 LLMResponse，未命中返回 None"""
        key = self._make_key(messages, tools)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        timestamp, response = entry

        # 检查 TTL
        if self._ttl > 0 and (time.time() - timestamp) > self._ttl:
            del self._cache[key]
            self._misses += 1
            return None

        # 命中：移到末尾（LRU）
        self._cache.move_to_end(key)
        self._hits += 1
        return response

    def put(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        response: LLMResponse,
    ) -> None:
        """写入缓存"""
        # 不缓存工具调用响应（因为工具结果可能变化）
        if response.has_tool_calls:
            return

        key = self._make_key(messages, tools)
        self._cache[key] = (time.time(), response)
        self._cache.move_to_end(key)

        # LRU 淘汰
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict:
        """缓存统计"""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / total:.1%}" if total > 0 else "N/A",
        }
