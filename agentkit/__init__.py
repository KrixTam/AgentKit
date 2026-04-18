"""
agentkit — Python 原生 Agent 框架，内置一等公民 Skill 支持

用法:
    from agentkit import Agent, Runner, function_tool
    from agentkit import Skill, load_skill_from_dir
    from agentkit import LLMRegistry, LLMConfig
"""
from .agents.agent import Agent
from .agents.base_agent import BaseAgent
from .agents.orchestrators import LoopAgent, ParallelAgent, SequentialAgent
from .llm.base import BaseLLM
from .llm.registry import LLMRegistry
from .llm.types import LLMConfig, LLMResponse, Message, ToolCall, ToolDefinition
from .memory.base import BaseMemoryProvider, Memory
from .runner.events import Event, RunResult
from .runner.runner import Runner
from .safety.guardrails import (
    GuardrailResult,
    InputGuardrail,
    OutputGuardrail,
    input_guardrail,
    output_guardrail,
)
from .safety.permissions import PermissionPolicy
from .skills.loader import load_skill_from_dir
from .skills.models import Skill, SkillFrontmatter, SkillResources
from .skills.registry import SkillRegistry
from .tools.base_tool import BaseTool, BaseToolset
from .tools.function_tool import FunctionTool, function_tool
from .tools.structured_data import ResultFormatter, StructuredDataTool
from .tools.sqlite_tool import SQLiteTool, SQLiteResultFormatter

__version__ = "0.4.1"


def get_docs_dir() -> str:
    """返回 agentkit 文档目录的绝对路径"""
    import os
    return os.path.join(os.path.dirname(__file__), "docs")


def get_examples_dir() -> str:
    """返回 agentkit 示例目录的绝对路径"""
    import os
    return os.path.join(os.path.dirname(__file__), "examples")


__all__ = [
    "Agent", "BaseAgent", "SequentialAgent", "ParallelAgent", "LoopAgent",
    "Runner", "RunResult", "Event",
    "BaseLLM", "LLMConfig", "LLMRegistry", "LLMResponse", "Message", "ToolCall", "ToolDefinition",
    "BaseTool", "BaseToolset", "FunctionTool", "function_tool", "StructuredDataTool", "ResultFormatter", "SQLiteTool",
    "Skill", "SkillFrontmatter", "SkillResources", "SkillRegistry", "load_skill_from_dir",
    "GuardrailResult", "InputGuardrail", "OutputGuardrail", "PermissionPolicy",
    "input_guardrail", "output_guardrail",
    "BaseMemoryProvider", "Memory",
    "get_docs_dir", "get_examples_dir",
]
