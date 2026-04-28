"""
agentkit/tools/skill_toolset.py — SkillToolset：Skill → Tool 桥接器

把 Skill 体系暴露为 4 个标准工具，让 LLM 通过 function calling 自主使用 Skill：
  1. list_skills    — 列出可用 Skill (L1)
  2. load_skill     — 加载 Skill 指令 (L2)
  3. load_skill_resource — 加载资源 (L3)
  4. run_skill_script    — 执行脚本 (L3)
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import pathlib
import types
from typing import Any
from ..skills.models import Skill
from .base_tool import BaseTool, BaseToolset
from .function_tool import FunctionTool

logger = logging.getLogger("agentkit.skill_toolset")


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
        self._entry_tool_cache: dict[tuple[str, str], BaseTool] = {}

    def set_additional_tools(self, tools: list[BaseTool]) -> None:
        """更新可供 Skill 动态注入的工具集合。"""
        self._additional_tools = {t.name: t for t in tools}

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
                    if tool_name in seen_tools:
                        continue
                    tool = self._additional_tools.get(tool_name)
                    if tool is None:
                        tool = self._load_tool_from_skill_entry(skill, tool_name)
                        if tool is not None:
                            self._additional_tools[tool_name] = tool
                    if tool is not None:
                        tools.append(tool)
                        seen_tools.add(tool_name)
        return tools

    def _load_tool_from_skill_entry(self, skill: Skill, tool_name: str) -> BaseTool | None:
        spec = next((item for item in skill.tool_specs if item.name == tool_name), None)
        if spec is None or not spec.entry:
            return None

        cache_key = (skill.name, tool_name)
        if cache_key in self._entry_tool_cache:
            return self._entry_tool_cache[cache_key]

        try:
            target = self._resolve_entry_target(skill, spec.entry)
            if isinstance(target, BaseTool):
                tool = target
            elif callable(target):
                tool = FunctionTool(
                    name=spec.name,
                    description=spec.description or "",
                    handler=target,
                    json_schema=self._build_json_schema(spec.parameters),
                    takes_context=self._callable_takes_context(target),
                )
            else:
                logger.warning(
                    "Skill '%s' tool '%s' entry '%s' 不是可调用对象",
                    skill.name,
                    tool_name,
                    spec.entry,
                )
                return None
        except Exception as exc:
            logger.warning(
                "加载 Skill '%s' tool '%s' entry '%s' 失败: %s",
                skill.name,
                tool_name,
                spec.entry,
                exc,
            )
            return None

        self._entry_tool_cache[cache_key] = tool
        return tool

    def _resolve_entry_target(self, skill: Skill, entry: str) -> Any:
        module_ref, attr_name = entry.split(":", 1)
        module_ref = module_ref.strip()
        attr_name = attr_name.strip()
        if not module_ref or not attr_name:
            raise ValueError("entry 格式必须为 '<module_or_path>:<attr>'")

        if module_ref.endswith(".py") or "/" in module_ref or module_ref.startswith("."):
            if not skill.source_dir:
                raise ValueError("Skill 未提供 source_dir，无法解析相对 entry 路径")
            file_path = pathlib.Path(module_ref)
            if not file_path.is_absolute():
                file_path = pathlib.Path(skill.source_dir) / file_path
            if not file_path.exists():
                raise FileNotFoundError(f"未找到 entry 文件: {file_path}")
            module_name = f"_agentkit_skill_{skill.name}_{attr_name}_{abs(hash(str(file_path)))}"
            module_spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if module_spec is None or module_spec.loader is None:
                raise ImportError(f"无法加载模块: {file_path}")
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
        else:
            module = importlib.import_module(module_ref)

        if not hasattr(module, attr_name):
            raise AttributeError(f"模块中不存在属性: {attr_name}")
        return getattr(module, attr_name)

    def _build_json_schema(self, params: dict[str, Any]) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for name, spec in (params or {}).items():
            if isinstance(spec, dict):
                properties[name] = dict(spec)
                if "type" not in properties[name]:
                    properties[name]["type"] = "string"
                if "default" not in properties[name]:
                    required.append(name)
            else:
                properties[name] = {"type": "string", "description": str(spec)}
                required.append(name)
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    def _callable_takes_context(self, fn: Any) -> bool:
        if not isinstance(fn, (types.FunctionType, types.MethodType)):
            return False
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        if not params:
            return False
        first = params[0]
        return first.name in {"ctx", "context", "run_context"}
