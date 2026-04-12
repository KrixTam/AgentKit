"""
agentkit/skills/loader.py — Skill 加载器

从本地目录加载 Skill（解析 SKILL.md 的 YAML Frontmatter + Markdown Body）。
"""
from __future__ import annotations

import pathlib
from typing import Union

import yaml

from .models import Skill, SkillFrontmatter, SkillResources, SkillScript


def load_skill_from_dir(skill_dir: Union[str, pathlib.Path]) -> Skill:
    """从目录加载 Skill"""
    skill_dir = pathlib.Path(skill_dir).resolve()
    skill_md_path = skill_dir / "SKILL.md"

    if not skill_md_path.exists():
        raise FileNotFoundError(f"未找到 SKILL.md: {skill_md_path}")

    content = skill_md_path.read_text(encoding="utf-8")

    # 解析 YAML Frontmatter
    if not content.startswith("---"):
        raise ValueError("SKILL.md 必须以 --- 开头的 YAML Frontmatter 开始")

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md 格式不正确：缺少 Frontmatter 结束标记 ---")

    frontmatter_yaml = parts[1]
    body = parts[2].strip()

    parsed = yaml.safe_load(frontmatter_yaml)
    frontmatter = SkillFrontmatter.model_validate(parsed)

    # 验证目录名与 Skill 名一致
    if skill_dir.name != frontmatter.name:
        raise ValueError(
            f"Skill 名 '{frontmatter.name}' 与目录名 '{skill_dir.name}' 不一致"
        )

    # 加载资源目录
    references = _load_dir_files(skill_dir / "references")
    assets = _load_dir_files(skill_dir / "assets")
    raw_scripts = _load_dir_files(skill_dir / "scripts")
    scripts = {
        name: SkillScript(
            filename=name,
            source=src if isinstance(src, str) else src.decode("utf-8"),
            language=_detect_language(name),
        )
        for name, src in raw_scripts.items()
    }

    return Skill(
        frontmatter=frontmatter,
        instructions=body,
        resources=SkillResources(references=references, assets=assets, scripts=scripts),
    )


def _load_dir_files(dir_path: pathlib.Path) -> dict[str, Union[str, bytes]]:
    """递归加载目录中的所有文件"""
    result: dict[str, Union[str, bytes]] = {}
    if not dir_path.exists():
        return result

    for file_path in dir_path.rglob("*"):
        if file_path.is_file():
            rel_path = str(file_path.relative_to(dir_path))
            try:
                result[rel_path] = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                result[rel_path] = file_path.read_bytes()

    return result


def _detect_language(filename: str) -> str:
    if filename.endswith(".py"):
        return "python"
    if filename.endswith((".sh", ".bash")):
        return "shell"
    if filename.endswith(".js"):
        return "javascript"
    return "unknown"
