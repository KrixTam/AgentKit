"""
agentkit/skills/models.py — Skill 数据模型

Skill = Frontmatter (L1) + Instructions (L2) + Resources (L3)
"""
from __future__ import annotations

import re
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator

from ..llm.types import LLMConfig


class SkillFrontmatter(BaseModel):
    """L1：Skill 元数据"""
    name: str
    description: str
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-z][a-z0-9-]{0,63}$", v):
            raise ValueError("name 必须是 kebab-case 格式，长度不超过 64 字符")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if len(v) > 1024:
            raise ValueError("description 不超过 1024 字符")
        return v

    @property
    def llm_config(self) -> Optional[LLMConfig]:
        raw = self.metadata.get("llm_config")
        if raw and isinstance(raw, dict):
            return LLMConfig(**raw)
        return None

    @property
    def additional_tools(self) -> list[str]:
        return self.metadata.get("additional_tools", [])


class SkillScript(BaseModel):
    """脚本包装器"""
    filename: str
    source: str
    language: str = "python"

    def __str__(self) -> str:
        return self.source


class SkillResources(BaseModel):
    """L3：Skill 资源"""
    references: dict[str, Union[str, bytes]] = Field(default_factory=dict)
    assets: dict[str, Union[str, bytes]] = Field(default_factory=dict)
    scripts: dict[str, SkillScript] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    def get_reference(self, name: str) -> Optional[Union[str, bytes]]:
        return self.references.get(name)

    def get_asset(self, name: str) -> Optional[Union[str, bytes]]:
        return self.assets.get(name)

    def get_script(self, name: str) -> Optional[SkillScript]:
        return self.scripts.get(name)

    def list_all(self) -> dict[str, list[str]]:
        return {
            "references": list(self.references.keys()),
            "assets": list(self.assets.keys()),
            "scripts": list(self.scripts.keys()),
        }


class Skill(BaseModel):
    """完整的 Skill = L1 + L2 + L3"""
    frontmatter: SkillFrontmatter
    instructions: str
    resources: SkillResources = Field(default_factory=SkillResources)
    
    # 资源与生命周期
    context: dict[str, Any] = Field(default_factory=dict, exclude=True)
    _is_loaded: bool = False
    
    # 生命周期钩子
    on_load_hook: Optional[Any] = Field(default=None, exclude=True)
    on_unload_hook: Optional[Any] = Field(default=None, exclude=True)
    
    model_config = {"arbitrary_types_allowed": True}

    async def on_load(self) -> None:
        """加载资源"""
        if self._is_loaded:
            return
        if self.on_load_hook:
            import inspect
            if inspect.iscoroutinefunction(self.on_load_hook):
                await self.on_load_hook(self)
            else:
                self.on_load_hook(self)
        self._is_loaded = True

    async def on_unload(self) -> None:
        """释放资源"""
        if not self._is_loaded:
            return
        if self.on_unload_hook:
            import inspect
            if inspect.iscoroutinefunction(self.on_unload_hook):
                await self.on_unload_hook(self)
            else:
                self.on_unload_hook(self)
        self._is_loaded = False
        self.context.clear()

    @property
    def name(self) -> str:
        return self.frontmatter.name

    @property
    def description(self) -> str:
        return self.frontmatter.description

    @property
    def additional_tools(self) -> list[str]:
        return self.frontmatter.additional_tools

    @property
    def llm_config(self) -> Optional[LLMConfig]:
        return self.frontmatter.llm_config
