"""
agentkit/skills/registry.py — Skill 注册中心
"""
from __future__ import annotations

import pathlib
from typing import Optional, Union

from .loader import load_skill_from_dir
from .models import Skill, SkillFrontmatter


class SkillRegistry:
    """Skill 注册中心——管理 Skill 的发现、加载、缓存"""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._search_paths: list[pathlib.Path] = []

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' 已注册")
        self._skills[skill.name] = skill

    def add_search_path(self, path: Union[str, pathlib.Path]) -> None:
        self._search_paths.append(pathlib.Path(path))

    def discover(self) -> list[Skill]:
        """从搜索路径中自动发现并加载所有 Skill"""
        for search_path in self._search_paths:
            if not search_path.exists():
                continue
            for skill_dir in search_path.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    if skill_dir.name not in self._skills:
                        skill = load_skill_from_dir(skill_dir)
                        self._skills[skill.name] = skill
        return list(self._skills.values())

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_all(self) -> list[SkillFrontmatter]:
        return [s.frontmatter for s in self._skills.values()]

    @property
    def skills(self) -> dict[str, Skill]:
        return dict(self._skills)
