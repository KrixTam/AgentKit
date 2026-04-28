from __future__ import annotations

import asyncio
from pathlib import Path

from agentkit.skills.loader import load_skill_from_dir
from agentkit.tools.skill_toolset import SkillToolset


def _write_skill_md(skill_dir: Path, content: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def test_skill_frontmatter_supports_triggers_dependencies_tools(tmp_path: Path):
    skill_dir = tmp_path / "demo-skill"
    _write_skill_md(
        skill_dir,
        """---
name: demo-skill
description: Demo skill
triggers:
  - "weather"
dependencies:
  - "common-utils"
tools:
  - "get_weather"
---
## Steps
Do something.
""",
    )

    skill = load_skill_from_dir(skill_dir)

    assert skill.triggers == ["weather"]
    assert skill.dependencies == ["common-utils"]
    assert skill.tools == ["get_weather"]
    assert skill.additional_tools == ["get_weather"]


def test_skill_frontmatter_tools_compatible_with_metadata_additional_tools(tmp_path: Path):
    skill_dir = tmp_path / "legacy-skill"
    _write_skill_md(
        skill_dir,
        """---
name: legacy-skill
description: Legacy skill
metadata:
  additional_tools:
    - "legacy_tool"
---
## Steps
Do legacy things.
""",
    )

    skill = load_skill_from_dir(skill_dir)
    assert skill.tools == []
    assert skill.additional_tools == ["legacy_tool"]


def test_skill_frontmatter_supports_object_tools_schema(tmp_path: Path):
    skill_dir = tmp_path / "schema-skill"
    _write_skill_md(
        skill_dir,
        """---
name: schema-skill
description: Schema tool skill
tools:
  - name: "tool_name"
    description: "工具功能简述"
    entry: "tools/tool_module.py:tool_function"
    parameters:
      param1: { type: string, description: "参数说明" }
      param2: { type: integer, default: 10, description: "可选参数" }
---
## Steps
Run structured tools.
""",
    )

    skill = load_skill_from_dir(skill_dir)

    assert skill.tools == ["tool_name"]
    assert skill.additional_tools == ["tool_name"]
    assert len(skill.tool_specs) == 1
    spec = skill.tool_specs[0]
    assert spec.name == "tool_name"
    assert spec.entry == "tools/tool_module.py:tool_function"
    assert spec.parameters["param2"]["default"] == 10


def test_skill_tool_entry_is_discovered_and_registered(tmp_path: Path):
    skill_dir = tmp_path / "entry-skill"
    _write_skill_md(
        skill_dir,
        """---
name: entry-skill
description: Entry tool skill
tools:
  - name: "tool_name"
    description: "工具功能简述"
    entry: "tools/tool_module.py:tool_function"
    parameters:
      param1: { type: string, description: "参数说明" }
---
## Steps
Use entry tool.
""",
    )
    tools_dir = skill_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "tool_module.py").write_text(
        "def tool_function(param1: str) -> str:\n"
        "    return f'echo:{param1}'\n",
        encoding="utf-8",
    )

    skill = load_skill_from_dir(skill_dir)
    toolset = SkillToolset(skills=[skill])

    async def _case() -> None:
        tools_before = await toolset.get_tools(ctx=None)
        assert all(t.name != "tool_name" for t in tools_before)

        load_skill_tool = next(t for t in tools_before if t.name == "load_skill")
        await load_skill_tool.execute(ctx=None, arguments={"skill_name": "entry-skill"})

        tools_after = await toolset.get_tools(ctx=None)
        dynamic_tool = next(t for t in tools_after if t.name == "tool_name")
        result = await dynamic_tool.execute(ctx=None, arguments={"param1": "ok"})
        assert result == "echo:ok"

    asyncio.run(_case())
