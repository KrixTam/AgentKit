"""
agentkit/skills/models.py — Skill 数据模型

Skill = Frontmatter (L1) + Instructions (L2) + Resources (L3)
"""
from __future__ import annotations

import re
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator

from ..llm.types import LLMConfig


class SkillToolSpec(BaseModel):
    """Skill frontmatter 中声明的工具规范。"""

    name: str
    description: Optional[str] = None
    entry: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        name = v.strip()
        if not name:
            raise ValueError("tool.name 不能为空")
        return name


class SkillFrontmatter(BaseModel):
    """L1：Skill 元数据"""
    name: str
    description: str
    license: Optional[str] = None
    compatibility: Optional[str] = None
    triggers: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    tools: list[SkillToolSpec] = Field(default_factory=list)
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

    @field_validator("triggers", "dependencies", mode="before")
    @classmethod
    def normalize_string_list(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("必须是字符串列表")
        result: list[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("必须是字符串列表")
            text = item.strip()
            if text:
                result.append(text)
        return result

    @field_validator("tools", mode="before")
    @classmethod
    def normalize_tools(cls, v: Any) -> list[dict[str, Any]]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("tools 必须是列表")
        result: list[dict[str, Any]] = []
        for item in v:
            if isinstance(item, str):
                name = item.strip()
                if name:
                    result.append({"name": name})
                continue
            if isinstance(item, dict):
                result.append(item)
                continue
            raise ValueError("tools 列表项必须是字符串或对象")
        return result

    @property
    def llm_config(self) -> Optional[LLMConfig]:
        raw = self.metadata.get("llm_config")
        if raw and isinstance(raw, dict):
            return LLMConfig(**raw)
        return None

    @property
    def additional_tools(self) -> list[str]:
        if self.tools:
            return [tool.name for tool in self.tools]
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
    source_dir: Optional[str] = Field(default=None, exclude=True)
    
    # 资源与生命周期
    context: dict[str, Any] = Field(default_factory=dict, exclude=True)
    _is_loaded: bool = False
    
    # 生命周期钩子
    on_load_hook: Optional[Any] = Field(default=None, exclude=True)
    on_unload_hook: Optional[Any] = Field(default=None, exclude=True)
    
    model_config = {"arbitrary_types_allowed": True}

    def get_context(self, ctx: Optional[Any] = None) -> dict[str, Any]:
        """获取 Skill 的上下文。优先从 RunContext 获取会话级上下文，回退到全局上下文"""
        if ctx is not None and hasattr(ctx, "state"):
            return ctx.state.setdefault(f"__skill_context_{self.name}__", {})
        return self.context

    async def on_load(self, ctx: Optional["RunContext"] = None) -> None:
        """加载资源"""
        if self._is_loaded:
            return
        if self.on_load_hook:
            import inspect
            if inspect.iscoroutinefunction(self.on_load_hook):
                await self.on_load_hook(self, ctx) if 'ctx' in inspect.signature(self.on_load_hook).parameters else await self.on_load_hook(self)
            else:
                self.on_load_hook(self, ctx) if 'ctx' in inspect.signature(self.on_load_hook).parameters else self.on_load_hook(self)
        self._is_loaded = True

    async def on_unload(self, ctx: Optional["RunContext"] = None) -> None:
        """释放资源"""
        if not self._is_loaded:
            return
        if self.on_unload_hook:
            import inspect
            if inspect.iscoroutinefunction(self.on_unload_hook):
                await self.on_unload_hook(self, ctx) if 'ctx' in inspect.signature(self.on_unload_hook).parameters else await self.on_unload_hook(self)
            else:
                self.on_unload_hook(self, ctx) if 'ctx' in inspect.signature(self.on_unload_hook).parameters else self.on_unload_hook(self)
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
    def triggers(self) -> list[str]:
        return self.frontmatter.triggers

    @property
    def dependencies(self) -> list[str]:
        return self.frontmatter.dependencies

    @property
    def tools(self) -> list[str]:
        return [tool.name for tool in self.frontmatter.tools]

    @property
    def tool_specs(self) -> list[SkillToolSpec]:
        return self.frontmatter.tools

    @property
    def llm_config(self) -> Optional[LLMConfig]:
        return self.frontmatter.llm_config
