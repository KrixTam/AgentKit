"""
agentkit/agents/agent.py — 核心 LLM Agent

开发者 99% 情况下使用的类。融合：
- OpenAI 的声明式配置
- Google 的丰富回调
- Skill 一等公民
- Handoff + as_tool 双协作模式
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, AsyncGenerator, Callable, Optional, Union

from pydantic import ConfigDict, Field, PrivateAttr

from ..llm.base import BaseLLM
from ..llm.registry import LLMRegistry
from ..llm.types import LLMConfig, Message, MessageRole, ToolCall as LLMToolCall
from ..runner.events import Event, EventType
from ..skills.models import Skill
from ..tools.base_tool import BaseTool, BaseToolset, HumanInputRequested
from ..tools.function_tool import FunctionTool
from ..tools.skill_toolset import SkillToolset
from .base_agent import BaseAgent

from ..runner.context import RunContext

logger = logging.getLogger("agentkit.agent")


class Agent(BaseAgent):
    """核心 LLM Agent"""

    # === LLM 配置 ===
    model: Union[str, LLMConfig, BaseLLM, None] = ""
    instructions: Union[str, Callable] = ""

    # === 工具 & 技能 ===
    tools: list[Any] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)

    # === Agent 间协作 ===
    handoffs: list[Any] = Field(default_factory=list)

    # === 输入输出 ===
    output_type: Optional[type] = None

    # === 安全 ===
    input_guardrails: list[Any] = Field(default_factory=list)
    output_guardrails: list[Any] = Field(default_factory=list)
    permission_policy: Optional[Any] = None

    # === 记忆 ===
    memory: Optional[Any] = None

    # === 行为 ===
    tool_use_behavior: str = "run_llm_again"
    max_tool_rounds: int = 20
    enable_cache: bool = True           # LLM 响应缓存（默认开启，绑定 Agent 实例生命周期）
    cache_ttl: int = 300                # 缓存有效期（秒）
    memory_async_write: bool = True     # 记忆写入是否异步（True=不阻塞, False=等写完再返回）

    # === 精细回调 ===
    before_model_callback: Optional[Callable] = None
    after_model_callback: Optional[Callable] = None
    before_tool_callback: Optional[Callable] = None
    after_tool_callback: Optional[Callable] = None
    before_handoff_callback: Optional[Callable] = None
    after_handoff_callback: Optional[Callable] = None
    on_error_callback: Optional[Callable] = None
    fail_fast_on_hook_error: bool = False

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    async def get_instructions(self, ctx: "RunContext") -> str:
        """获取系统提示词（支持动态函数）"""
        if callable(self.instructions):
            result = self.instructions(ctx, self)
            if inspect.isawaitable(result):
                return await result
            return result
        return self.instructions or ""

    async def get_all_tools(self, ctx: "RunContext") -> list[BaseTool]:
        """汇总所有可用工具"""
        all_tools: list[BaseTool] = []

        # 1. 处理 tools
        for tool_union in self.tools:
            if isinstance(tool_union, BaseTool):
                all_tools.append(tool_union)
            elif isinstance(tool_union, BaseToolset):
                all_tools.extend(await tool_union.get_tools(ctx))
            elif callable(tool_union):
                all_tools.append(FunctionTool.from_function(tool_union))

        # 2. 处理 skills → SkillToolset
        if self.skills:
            additional = [t for t in all_tools]  # 让 Skill 能看到已注册的工具
            skill_toolset = SkillToolset(skills=self.skills, additional_tools=additional)
            all_tools.extend(await skill_toolset.get_tools(ctx))

        # 3. 处理 handoffs → transfer_to_xxx 工具
        for target in self.handoffs:
            if isinstance(target, BaseAgent):
                all_tools.append(self._create_handoff_tool(target))

        return all_tools

    def as_tool(self, name: str, description: str) -> FunctionTool:
        """把自己变成一个工具，供其他 Agent 调用"""
        agent_ref = self

        async def _invoke(**kwargs: Any) -> Any:
            input_text = kwargs.get("input", "")
            from ..runner.runner import Runner
            result = await Runner.run(agent_ref, input=str(input_text))
            return result.final_output

        return FunctionTool(
            name=name,
            description=description,
            handler=_invoke,
            json_schema={
                "type": "object",
                "properties": {"input": {"type": "string", "description": "任务输入"}},
                "required": ["input"],
            },
        )

    # ------------------------------------------------------------------
    # 核心执行循环
    # ------------------------------------------------------------------

    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator[Event, None]:
        round_count = 0

        # 在执行前加载所有未加载的 Skill
        for skill in self.skills:
            try:
                await skill.on_load(ctx)
            except Exception as e:
                yield Event(
                    agent=self.name, 
                    type="error", 
                    data={"context": "skill_on_load", "skill": skill.name, "error": str(e)}
                )

        try:
            while round_count < self.max_tool_rounds:
                round_count += 1

                # 1. 构建指令
                instructions = await self.get_instructions(ctx)

                # 注入记忆
                if self.memory:
                    try:
                        relevant = await self.memory.search(ctx.input, user_id=ctx.user_id, agent_id=self.name, limit=5)
                        if relevant:
                            mem_text = "\n".join([f"- {m.content}" for m in relevant])
                            instructions += f"\n\n## 相关记忆\n{mem_text}"
                    except Exception as e:
                        logger.warning("检索记忆失败: %s", e)

                # 注入 Skill 列表
                if self.skills:
                    skill_toolset = SkillToolset(skills=self.skills)
                    instructions += "\n\n" + skill_toolset.get_system_prompt_injection()

                # 2. 获取工具
                tools = await self.get_all_tools(ctx)
                tool_defs = [t.to_tool_definition() for t in tools]

                # 3. 构建消息
                messages = [Message.system(instructions)]
                messages.append(Message.user(ctx.input))

                # 追加历史消息
                for msg_dict in ctx.get_messages():
                    role = MessageRole(msg_dict.get("role", "user"))
                    tool_calls_raw = msg_dict.get("tool_calls", [])
                    tool_calls_parsed = [
                        LLMToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                        for tc in tool_calls_raw
                    ] if tool_calls_raw else []
                    messages.append(Message(
                        role=role,
                        content=msg_dict.get("content"),
                        tool_call_id=msg_dict.get("tool_call_id"),
                        tool_calls=tool_calls_parsed,
                    ))

                # 4. before_model 回调
                if self.before_model_callback:
                    override, duration, err = await self._run_hook(self.before_model_callback, "before_model_callback", ctx, instructions, tools)
                    if err:
                        yield Event(agent=self.name, type="error", data={"hook": "before_model", "error": str(err), "duration": duration})
                        if self.fail_fast_on_hook_error:
                            return
                    elif override is not None:
                        yield Event(agent=self.name, type="model_override", data={"override": override, "duration": duration})
                        return

                # 5. 调用 LLM（支持缓存）
                llm = self._resolve_model()
                cached = False

                # 检查缓存
                if self.enable_cache:
                    cache = self._get_cache()
                    cached_response = cache.get(messages, tool_defs if tool_defs else None)
                    if cached_response is not None:
                        response = cached_response
                        cached = True

                if not cached:
                    try:
                        response = await llm.generate(messages=messages, tools=tool_defs if tool_defs else None)
                    except Exception as e:
                        error_msg = str(e) or f"{type(e).__name__}: LLM 调用失败"
                        if self.on_error_callback:
                            _, duration, err = await self._run_hook(self.on_error_callback, "on_error_callback", ctx, e)
                            if err:
                                yield Event(agent=self.name, type="error", data={"hook": "on_error", "error": str(err), "duration": duration})
                                if self.fail_fast_on_hook_error:
                                    return
                        yield Event(agent=self.name, type="error", data=error_msg)
                        return

                    # 写入缓存
                    if self.enable_cache:
                        cache.put(messages, tool_defs if tool_defs else None, response)

                # 6. after_model 回调
                if self.after_model_callback:
                    hook_res, duration, err = await self._run_hook(self.after_model_callback, "after_model_callback", ctx, response)
                    if err:
                        yield Event(agent=self.name, type="error", data={"hook": "after_model", "error": str(err), "duration": duration})
                        if self.fail_fast_on_hook_error:
                            return
                    elif hook_res is not None:
                        response = hook_res

                yield Event(agent=self.name, type="llm_response", data=response)

                # 7. 分析响应
                if response.has_tool_calls:
                    # ⭐ 关键：先把 assistant 的 tool_calls 加入历史，
                    # 这样下一轮 LLM 能看到完整的调用链（assistant→tool→assistant...）
                    ctx.messages.append({
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": [
                            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                            for tc in response.tool_calls
                        ],
                    })

                    for tool_call in response.tool_calls:
                        tool = self._find_tool(tools, tool_call.name)
                        if not tool:
                            yield Event(agent=self.name, type="error", data=f"工具 '{tool_call.name}' 未找到")
                            continue

                        # 检查是否是 handoff
                        if tool_call.name.startswith("transfer_to_"):
                            target_agent = tool_call.name.replace("transfer_to_", "")
                            
                            # before_handoff 回调
                            if self.before_handoff_callback:
                                override, duration, err = await self._run_hook(self.before_handoff_callback, "before_handoff_callback", ctx, target_agent, tool_call)
                                if err:
                                    yield Event(agent=self.name, type="error", data={"hook": "before_handoff", "error": str(err), "duration": duration})
                                    if self.fail_fast_on_hook_error:
                                        return
                                elif override is not None:
                                    target_agent = override
                            
                            # 保持 tool-call 消息链完整，避免后续 Agent 看到未闭合的 tool_call
                            # 导致模型输出空内容 (content=None)。
                            ctx.add_tool_result(tool_call.id, f"Handoff to {target_agent}")
                            
                            # after_handoff 回调
                            if self.after_handoff_callback:
                                _, duration, err = await self._run_hook(self.after_handoff_callback, "after_handoff_callback", ctx, target_agent)
                                if err:
                                    yield Event(agent=self.name, type="error", data={"hook": "after_handoff", "error": str(err), "duration": duration})
                                    if self.fail_fast_on_hook_error:
                                        return
                            
                            yield Event(agent=self.name, type="handoff", data={"target": target_agent})
                            return

                        # before_tool 回调
                        if self.before_tool_callback:
                            override, duration, err = await self._run_hook(self.before_tool_callback, "before_tool_callback", ctx, tool, tool_call)
                            if err:
                                yield Event(agent=self.name, type="error", data={"hook": "before_tool", "error": str(err), "duration": duration})
                                if self.fail_fast_on_hook_error:
                                    return
                            elif override is not None:
                                continue

                        # 权限检查
                        if self.permission_policy:
                            allowed = await self.permission_policy.check(tool.name, tool_call.arguments)
                            if not allowed:
                                yield Event(agent=self.name, type="permission_denied", data={"tool": tool_call.name})
                                ctx.add_tool_result(tool_call.id, "Permission denied")
                                continue

                        # 执行工具
                        try:
                            result = await tool.execute(ctx, tool_call.arguments)
                        except HumanInputRequested as e:
                            # 触发挂起事件，并记录挂起的工具信息
                            ctx.state["__suspended_tool_call_id__"] = tool_call.id
                            ctx.state["__suspended_tool_name__"] = tool_call.name
                            yield Event(
                                agent=self.name, 
                                type=EventType.SUSPEND_REQUESTED, 
                                data={"prompt": e.prompt, "tool": tool_call.name, "tool_call_id": tool_call.id, **e.kwargs}
                            )
                            return
                        except Exception as e:
                            result = f"工具执行错误: {e}"

                        # after_tool 回调
                        if self.after_tool_callback:
                            hook_res, duration, err = await self._run_hook(self.after_tool_callback, "after_tool_callback", ctx, tool, result)
                            if err:
                                yield Event(agent=self.name, type="error", data={"hook": "after_tool", "error": str(err), "duration": duration})
                                if self.fail_fast_on_hook_error:
                                    return
                            elif hook_res is not None:
                                result = hook_res

                        yield Event(agent=self.name, type="tool_result", data={"tool": tool_call.name, "result": result})
                        ctx.add_tool_result(tool_call.id, result)

                    if self.tool_use_behavior == "stop":
                        return
                    continue  # run_llm_again

                else:
                    # 最终输出
                    output = response.content

                    # 存储记忆
                    if self.memory and output:
                        conversation = f"User: {ctx.input}\nAssistant: {output}"
                        if self.memory_async_write:
                            # fire-and-forget：不阻塞返回，后台异步写入（更快）
                            import asyncio

                            async def _save_memory():
                                try:
                                    await self.memory.add(conversation, user_id=ctx.user_id, agent_id=self.name)
                                except Exception as e:
                                    logger.warning("存储记忆失败: %s", e)

                            asyncio.create_task(_save_memory())
                        else:
                            # 同步等待写入完成（适合需要即时读取记忆的场景）
                            try:
                                await self.memory.add(conversation, user_id=ctx.user_id, agent_id=self.name)
                            except Exception as e:
                                logger.warning("存储记忆失败: %s", e)

                    yield Event(agent=self.name, type="final_output", data=output)
                    return

            yield Event(agent=self.name, type="error", data=f"超过最大工具调用轮次 {self.max_tool_rounds}")
        finally:
            for skill in self.skills:
                try:
                    import time
                    start_time = time.time()
                    await skill.on_unload(ctx)
                    duration = time.time() - start_time
                    logger.info(f"[{self.name}] resource_released: skill={skill.name} duration={duration:.4f}s session={ctx.session_id}")
                except Exception as e:
                    logger.error(f"[{self.name}] skill_on_unload error: skill={skill.name} error={e}")

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """清空 LLM 响应缓存"""
        if self._cache_instance is not None:
            self._cache_instance.clear()

    _cache_instance: Any = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_cache(self):
        """获取或创建缓存实例（懒初始化）"""
        if self._cache_instance is None:
            from ..llm.cache import LLMCache
            self._cache_instance = LLMCache(max_size=128, ttl=self.cache_ttl)
        return self._cache_instance

    def _resolve_model(self) -> BaseLLM:
        if isinstance(self.model, BaseLLM):
            return self.model
        if self.model:
            return LLMRegistry.create(self.model)
        # 向上继承
        ancestor = self.parent_agent
        while ancestor:
            if isinstance(ancestor, Agent) and ancestor.model:
                return ancestor._resolve_model()
            ancestor = ancestor.parent_agent
        return LLMRegistry.create_default()

    @staticmethod
    def _find_tool(tools: list[BaseTool], name: str) -> BaseTool | None:
        for tool in tools:
            if tool.name == name:
                return tool
        return None

    @staticmethod
    def _create_handoff_tool(target: BaseAgent) -> FunctionTool:
        async def _handler(**_kwargs: Any) -> str:
            return f"Handoff to {target.name}"

        return FunctionTool(
            name=f"transfer_to_{target.name}",
            description=f"将对话交给 {target.description or target.name}",
            handler=_handler,
            json_schema={
                "type": "object",
                "properties": {"reason": {"type": "string", "description": "转交原因"}},
            },
        )
