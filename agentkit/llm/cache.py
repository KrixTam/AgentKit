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
import logging
import time
from collections import OrderedDict
from typing import Optional

from .types import LLMResponse, Message, ToolDefinition

logger = logging.getLogger("agentkit.llm.cache")


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
        self._msg_fp_cache: dict[int, tuple[tuple, str]] = {}
        self._tool_fp_cache: dict[int, tuple[tuple, str]] = {}
        self._key_gen_calls = 0
        self._key_gen_total_ms = 0.0
        self._key_gen_last_ms = 0.0

    def _message_fingerprint(self, msg: Message) -> str:
        tool_calls_sig = tuple(
            (tc.id, tc.name, json.dumps(tc.arguments, sort_keys=True))
            for tc in (msg.tool_calls or [])
        )
        sig = (msg.role.value, msg.content or "", msg.tool_call_id or "", tool_calls_sig)
        cache_key = id(msg)
        cached = self._msg_fp_cache.get(cache_key)
        if cached and cached[0] == sig:
            return cached[1]
        fp = hashlib.sha1(repr(sig).encode()).hexdigest()
        self._msg_fp_cache[cache_key] = (sig, fp)
        if len(self._msg_fp_cache) > 8192:
            self._msg_fp_cache.clear()
        return fp

    def _tool_fingerprint(self, tool: ToolDefinition) -> str:
        sig = (tool.name, json.dumps(tool.parameters, sort_keys=True))
        cache_key = id(tool)
        cached = self._tool_fp_cache.get(cache_key)
        if cached and cached[0] == sig:
            return cached[1]
        fp = hashlib.sha1(repr(sig).encode()).hexdigest()
        self._tool_fp_cache[cache_key] = (sig, fp)
        if len(self._tool_fp_cache) > 4096:
            self._tool_fp_cache.clear()
        return fp

    def _make_key(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> str:
        """根据消息和工具列表生成缓存 key"""
        start = time.perf_counter()
        hasher = hashlib.sha256()
        for msg in messages:
            hasher.update(self._message_fingerprint(msg).encode())
            hasher.update(b"|")
        if tools:
            for tool in tools:
                hasher.update(self._tool_fingerprint(tool).encode())
                hasher.update(b"|")
        key = hasher.hexdigest()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self._key_gen_calls += 1
        self._key_gen_total_ms += elapsed_ms
        self._key_gen_last_ms = elapsed_ms
        logger.debug(
            "cache_key_generated messages=%s tools=%s elapsed_ms=%.3f",
            len(messages),
            len(tools or []),
            elapsed_ms,
        )
        return key

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
        self._key_gen_calls = 0
        self._key_gen_total_ms = 0.0
        self._key_gen_last_ms = 0.0

    @property
    def last_key_gen_ms(self) -> float:
        return self._key_gen_last_ms

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
            "key_gen_calls": self._key_gen_calls,
            "key_gen_total_ms": round(self._key_gen_total_ms, 3),
            "key_gen_last_ms": round(self._key_gen_last_ms, 3),
            "key_gen_avg_ms": round(self._key_gen_total_ms / self._key_gen_calls, 3) if self._key_gen_calls else 0.0,
        }
