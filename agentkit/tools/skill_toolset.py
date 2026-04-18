"""
agentkit/tools/skill_toolset.py — SkillToolset：Skill → Tool 桥接器

把 Skill 体系暴露为 4 个标准工具，让 LLM 通过 function calling 自主使用 Skill：
  1. list_skills    — 列出可用 Skill (L1)
  2. load_skill     — 加载 Skill 指令 (L2)
  3. load_skill_resource — 加载资源 (L3)
  4. run_skill_script    — 执行脚本 (L3)
"""
from __future__ import annotations

from typing import Any
from ..skills.models import Skill
from .base_tool import BaseTool, BaseToolset
from .function_tool import FunctionTool


class SkillToolset(BaseToolset):
    """Skill → Tool 桥接器"""

    def __init__(
        self,
        skills: list[Skill],
        additional_tools: list[BaseTool] | None = None,
    ):
        self._skills: dict[str, Skill] = {s.name: s for s in skills}
        self._additional_tools: dict[str, BaseTool] = {t.name: t for t in (additional_tools or [])}
        self._activated_skills: set[str] = set()

    async def get_tools(self, ctx: Any) -> list[BaseTool]:
        base_tools = [
            self._make_list_skills_tool(),
            self._make_load_skill_tool(),
            self._make_load_resource_tool(),
            self._make_run_script_tool(),
        ]
        dynamic = self._get_additional_tools_for_activated_skills()
        return base_tools + dynamic

    def get_system_prompt_injection(self) -> str:
        """生成注入到 LLM 系统提示词中的 Skill 列表"""
        lines = ["<available_skills>"]
        for skill in self._skills.values():
            lines.append("<skill>")
            lines.append(f"  <name>{skill.name}</name>")
            lines.append(f"  <description>{skill.description}</description>")
            lines.append("</skill>")
        lines.append("</available_skills>")
        skills_xml = "\n".join(lines)

        return (
            "你可以使用专业技能（Skill）来完成复杂任务。\n\n"
            f"{skills_xml}\n"
            "使用规则：\n"
            "1. 如果某个 Skill 与用户请求相关，先调用 `load_skill` 加载其详细指令\n"
            "2. 加载后，严格按照指令步骤执行\n"
            "3. 需要参考资料时，使用 `load_skill_resource` 按需加载\n"
            "4. 需要执行脚本时，使用 `run_skill_script`\n"
            "5. 不要凭猜测使用 Skill，先加载指令再行动\n"
        )

    # ------------------------------------------------------------------
    # 四个桥接工具
    # ------------------------------------------------------------------

    def _make_list_skills_tool(self) -> FunctionTool:
        skills_ref = self._skills

        async def handler(**_kwargs: Any) -> str:
            lines = ["<available_skills>"]
            for skill in skills_ref.values():
                lines.append(f"  <skill>")
                lines.append(f"    <name>{skill.name}</name>")
                lines.append(f"    <description>{skill.description}</description>")
                lines.append(f"  </skill>")
            lines.append("</available_skills>")
            return "\n".join(lines)

        return FunctionTool(
            name="list_skills",
            description="列出所有可用的专业技能（Skill）",
            handler=handler,
            json_schema={"type": "object", "properties": {}},
        )

    def _make_load_skill_tool(self) -> FunctionTool:
        skills_ref = self._skills
        activated = self._activated_skills

        async def handler(skill_name: str = "", **_kwargs: Any) -> dict | str:
            skill = skills_ref.get(skill_name)
            if not skill:
                return f"Error: Skill '{skill_name}' not found"
            activated.add(skill_name)
            result: dict[str, Any] = {
                "skill_name": skill_name,
                "instructions": skill.instructions,
                "available_resources": skill.resources.list_all(),
            }
            if skill.llm_config:
                result["llm_hint"] = {
                    "model": skill.llm_config.model,
                    "note": f"此 Skill 建议使用 {skill.llm_config.model} 执行",
                }
            return result

        return FunctionTool(
            name="load_skill",
            description="加载指定 Skill 的详细操作指令。使用前必须先加载。",
            handler=handler,
            json_schema={
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string", "description": "Skill 名称"},
                },
                "required": ["skill_name"],
            },
        )

    def _make_load_resource_tool(self) -> FunctionTool:
        skills_ref = self._skills

        async def handler(skill_name: str = "", path: str = "", **_kwargs: Any) -> dict | str:
            skill = skills_ref.get(skill_name)
            if not skill:
                return f"Error: Skill '{skill_name}' not found"

            parts = path.split("/", 1)
            category = parts[0]
            filename = parts[1] if len(parts) > 1 else ""

            content: Any = None
            if category == "references":
                content = skill.resources.get_reference(filename)
            elif category == "assets":
                content = skill.resources.get_asset(filename)
            elif category == "scripts":
                script = skill.resources.get_script(filename)
                content = script.source if script else None
            else:
                return f"Error: 未知资源类型 '{category}'"

            if content is None:
                return f"Error: 资源 '{path}' 不存在"
            return {"skill_name": skill_name, "path": path, "content": content}

        return FunctionTool(
            name="load_skill_resource",
            description="加载 Skill 的参考文档、资源文件或脚本源码",
            handler=handler,
            json_schema={
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"},
                    "path": {"type": "string", "description": "资源路径，如 references/api_doc.md"},
                },
                "required": ["skill_name", "path"],
            },
        )

    def _make_run_script_tool(self) -> FunctionTool:
        skills_ref = self._skills

        async def handler(skill_name: str = "", script_name: str = "", arguments: dict | None = None, **_kwargs: Any) -> str:
            skill = skills_ref.get(skill_name)
            if not skill:
                return f"Error: Skill '{skill_name}' not found"
            script = skill.resources.get_script(script_name)
            if not script:
                return f"Error: 脚本 '{script_name}' 不存在"
            # TODO: 通过 SandboxExecutor 执行
            return f"[脚本执行占位] {script_name} with args: {arguments}"

        return FunctionTool(
            name="run_skill_script",
            description="执行 Skill 中的脚本文件",
            handler=handler,
            json_schema={
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"},
                    "script_name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["skill_name", "script_name"],
            },
        )

    # ------------------------------------------------------------------
    # 动态工具注入
    # ------------------------------------------------------------------

    def _get_additional_tools_for_activated_skills(self) -> list[BaseTool]:
        tools: list[BaseTool] = []
        seen_tools: set[str] = set()
        for skill_name in self._activated_skills:
            skill = self._skills.get(skill_name)
            if skill:
                for tool_name in skill.additional_tools:
                    if tool_name in self._additional_tools and tool_name not in seen_tools:
                        tools.append(self._additional_tools[tool_name])
                        seen_tools.add(tool_name)
        return tools
