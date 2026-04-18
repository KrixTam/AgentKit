"""
agentkit/runner/context_store.py — Context Store 协议及实现

提供 Runner 上下文的持久化与恢复能力。
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

from .context import RunContext


class ContextStore(ABC):
    """上下文存储协议"""
    
    @abstractmethod
    def save(self, session_id: str, context: RunContext) -> None:
        """保存上下文"""
        pass
        
    @abstractmethod
    def load(self, session_id: str, shared_context_cls: Optional[Any] = None) -> Optional[RunContext]:
        """加载上下文"""
        pass
        
    @abstractmethod
    def delete(self, session_id: str) -> None:
        """删除上下文"""
        pass


class InMemoryContextStore(ContextStore):
    """内存中的上下文存储"""
    
    def __init__(self):
        self._store: dict[str, RunContext] = {}
        
    def save(self, session_id: str, context: RunContext) -> None:
        self._store[session_id] = context
        
    def load(self, session_id: str, shared_context_cls: Optional[Any] = None) -> Optional[RunContext]:
        # 对于内存存储，直接返回对象引用，或者反序列化一个拷贝以防止污染
        if session_id in self._store:
            # 返回一份序列化后反序列化的副本以保证隔离性
            ctx = self._store[session_id]
            return RunContext.from_dict(ctx.to_dict(), shared_context_cls)
        return None
        
    def delete(self, session_id: str) -> None:
        if session_id in self._store:
            del self._store[session_id]


class FileContextStore(ContextStore):
    """基于文件的上下文存储"""
    
    def __init__(self, directory: str = ".agentkit_checkpoints"):
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)
        
    def _get_path(self, session_id: str) -> str:
        # 防护：只取合法的文件名
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ('-', '_'))
        return os.path.join(self.directory, f"{safe_id}.json")
        
    def save(self, session_id: str, context: RunContext) -> None:
        path = self._get_path(session_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(context.to_json())
            
    def load(self, session_id: str, shared_context_cls: Optional[Any] = None) -> Optional[RunContext]:
        path = self._get_path(session_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return RunContext.from_json(f.read(), shared_context_cls)
            
    def delete(self, session_id: str) -> None:
        path = self._get_path(session_id)
        if os.path.exists(path):
            os.remove(path)
