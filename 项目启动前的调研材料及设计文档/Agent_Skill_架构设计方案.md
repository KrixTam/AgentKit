# Agent + Skill 架构设计方案

> **设计者**：基于 Google ADK、OpenAI Agents SDK、Anthropic Claude Agent SDK 三大框架的源码分析  
> **设计目标**：取三家之长，设计一个 Python 原生的、轻量灵活的 Agent 框架，内置一等公民级别的 Skill 支持  
> **日期**：2026-04-09

---

## 目录

- [一、三大框架设计精华提炼](#一三大框架设计精华提炼)
- [二、设计原则](#二设计原则)
- [三、整体架构分层](#三整体架构分层)
- [四、Agent 层设计](#四agent-层设计)
  - [4.1 Agent 基类](#41-agent-基类)
  - [4.2 LLM Agent（核心 Agent）](#42-llm-agent核心-agent)
  - [4.3 编排 Agent（Orchestrator）](#43-编排-agentorchestrator)
  - [4.4 Agent 间协作：Handoff + as_tool 双模式](#44-agent-间协作handoff--as_tool-双模式)
- [五、Tool 层设计](#五tool-层设计)
  - [5.1 统一工具类型体系](#51-统一工具类型体系)
  - [5.2 @function_tool 装饰器](#52-function_tool-装饰器)
  - [5.3 MCP 集成](#53-mcp-集成)
- [六、Skill 层设计（核心创新）](#六skill-层设计核心创新)
  - [6.1 Skill 定位与结构标准](#61-skill-定位与结构标准)
  - [6.2 三级渐进式加载（L1/L2/L3）](#62-三级渐进式加载l1l2l3)
  - [6.3 Skill 数据模型](#63-skill-数据模型)
  - [6.4 SkillRegistry — Skill 的注册与发现](#64-skillregistry--skill-的注册与发现)
  - [6.5 SkillToolset — Skill 到工具的桥接](#65-skilltoolset--skill-到工具的桥接)
  - [6.6 Skill 的动态工具注入](#66-skill-的动态工具注入)
- [七、Runner 层设计](#七runner-层设计)
  - [7.1 Runner 核心循环](#71-runner-核心循环)
  - [7.2 RunContext — 运行上下文](#72-runcontext--运行上下文)
  - [7.3 Event 流式输出](#73-event-流式输出)
- [八、回调与安全机制](#八回调与安全机制)
  - [8.1 生命周期回调链](#81-生命周期回调链)
  - [8.2 Guardrail 安全护栏](#82-guardrail-安全护栏)
  - [8.3 权限控制](#83-权限控制)
- [九、完整使用示例](#九完整使用示例)
- [十、与三大框架的对比](#十与三大框架的对比)
- [十一、开放讨论点](#十一开放讨论点)

---

## 一、三大框架设计精华提炼

在动手设计之前，先总结三家框架各自最值得借鉴的设计点：

### Google ADK — 最成熟的 Skill 体系

| 精华 | 说明 |
|------|------|
| **三级渐进式加载** | L1（元数据）→ L2（指令）→ L3（资源），按需加载节省 token |
| **SkillToolset 桥接模式** | 把 Skill 转化为 4 个 LLM 可调用的标准工具 |
| **模板方法模式** | `run_async`（final）→ `_run_async_impl`（override），保证流程统一 |
| **Agent 树结构** | parent/sub_agents 形成编排树，支持 Sequential/Parallel/Loop |
| **工具统一化** | `Callable | BaseTool | BaseToolset` 三种形态统一接入 |

### OpenAI Agents SDK — 最轻量的 Agent 定义

| 精华 | 说明 |
|------|------|
| **Agent 即 dataclass** | 纯配置对象，不需要继承复杂的类层次 |
| **@function_tool 装饰器** | 一行代码把 Python 函数变成工具，自动推断 JSON Schema |
| **Handoff + as_tool 双模式** | Agent 既能接受交接（控制权转移），也能被当作工具调用 |
| **Guardrail 内置** | Input/Output 双向安全护栏，支持并行检查 |
| **tool_use_behavior** | 工具调用后的行为可配（再问 LLM / 直接返回 / 自定义） |

### Anthropic Claude Agent SDK — 最务实的 Skill 生态

| 精华 | 说明 |
|------|------|
| **纯文件即 Skill** | SKILL.md + 脚本 + 参考资料，拷贝即用 |
| **description 驱动触发** | 利用 LLM 的语义理解自动判断何时使用 Skill |
| **Hook 机制** | 丰富的事件钩子（PreToolUse/PostToolUse/Stop 等） |
| **权限控制分层** | 预设模式 + 白名单 + 自定义回调三种粒度 |
| **Skill Creator 元技能** | 用 Skill 创建 Skill 的自动化工作流 |

---

## 二、设计原则

基于三家的经验教训，本架构遵循以下原则：

| 原则 | 来源 | 解释 |
|------|------|------|
| **声明式优先** | OpenAI | Agent/Tool/Skill 都是配置对象，而非命令式代码 |
| **Skill 一等公民** | Google + Anthropic | Skill 不是 Tool 的子集，而是独立的能力抽象层 |
| **按需加载** | Google | 三级加载模型，避免 token 浪费 |
| **双协作模式** | OpenAI | 同时支持 Handoff（转介）和 as_tool（委派） |
| **模型无关** | All | 抽象 LLM 接口，不绑定特定厂商 |
| **回调可插拔** | Google + Anthropic | 生命周期每个环节都可拦截 |
| **安全内置** | OpenAI + Anthropic | Guardrail 和权限控制不是可选项 |
| **Python 原生** | All | 充分利用 Python 的 type hint、decorator、dataclass |

---

## 三、整体架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                     第 1 层：Application（应用层）                  │
│   Runner — 驱动 Agent 运行循环，管理 turn/handoff/event 流        │
│   RunContext — 一次运行的完整上下文（session/state/memory）        │
├──────────────────────────────────────────────────────────────────┤
│                     第 2 层：Agent（智能体层）                      │
│   Agent (LlmAgent) — 核心 LLM Agent                              │
│   SequentialAgent / ParallelAgent / LoopAgent — 编排 Agent        │
│   Handoff — Agent 间控制权转移                                     │
├──────────────────────────────────────────────────────────────────┤
│                     第 3 层：Skill（技能层）                       │
│   SkillRegistry — Skill 的注册、发现、生命周期管理                 │
│   SkillToolset — Skill → Tool 桥接器                              │
│   Skill 数据模型 (Frontmatter + Instructions + Resources)         │
├──────────────────────────────────────────────────────────────────┤
│                     第 4 层：Tool（工具层）                        │
│   FunctionTool / MCPTool / BuiltinTool                           │
│   @function_tool 装饰器 / Schema 自动推断                         │
├──────────────────────────────────────────────────────────────────┤
│                     第 5 层：Safety（安全层）                      │
│   InputGuardrail / OutputGuardrail — 双向安全护栏                 │
│   PermissionPolicy — 权限控制策略                                 │
│   Callback Chain — 生命周期回调链                                 │
├──────────────────────────────────────────────────────────────────┤
│                     第 6 层：Foundation（基础设施层）               │
│   LLM 接口抽象 (BaseLLM / LLMRegistry)                           │
│   Session / Memory / State / Artifact                             │
│   Tracing / Logging / Metrics                                     │
└──────────────────────────────────────────────────────────────────┘
```

**各层依赖关系**：

```
Application → Agent → Skill → Tool → Foundation
                ↓               ↓
              Safety          Safety
```

**关键设计决策**：Skill 层位于 Agent 和 Tool 之间，这是本架构的核心创新。Skill 既不是简单的 Tool 集合（那是 Google 的做法），也不是完全独立于 Agent 的外部系统（那是 Anthropic 的做法）。Skill 是一个中间抽象——它封装了**指令 + 资源 + 工具**的组合，通过 SkillToolset 桥接到 Agent。

---

## 四、Agent 层设计

### 4.1 Agent 基类

**设计取舍**：综合 Google 的 `BaseModel` 继承和 OpenAI 的 `dataclass` 风格。选择 **Pydantic BaseModel** 作为基类——既能享受 dataclass 的声明式简洁，又能利用 Pydantic 的校验、序列化能力。

```python
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator
from abc import abstractmethod

class BaseAgent(BaseModel):
    """所有 Agent 的基类"""
    
    # === 身份 ===
    name: str                                           # Agent 名称
    description: str = ""                               # Agent 描述（handoff/发现时使用）
    
    # === 树结构 ===
    parent_agent: Optional["BaseAgent"] = None          # 父 Agent（自动设置）
    sub_agents: list["BaseAgent"] = Field(default_factory=list)
    
    # === 生命周期回调 ===
    before_agent_callback: Optional[Callable] = None    # 运行前拦截
    after_agent_callback: Optional[Callable] = None     # 运行后拦截
    
    model_config = {"arbitrary_types_allowed": True}
    
    def model_post_init(self, __context):
        """初始化后自动建立父子关系"""
        for sub in self.sub_agents:
            if sub.parent_agent is not None:
                raise ValueError(f"Agent '{sub.name}' 已有父 Agent")
            sub.parent_agent = self
    
    # === 模板方法（借鉴 Google ADK）===
    async def run(self, ctx: "RunContext") -> AsyncGenerator["Event", None]:
        """
        运行入口 — 子类不可覆盖。
        保证了: before_callback → 核心逻辑 → after_callback 的统一流程。
        """
        # 1. 运行前回调
        if self.before_agent_callback:
            result = await self.before_agent_callback(ctx)
            if result is not None:
                yield Event(agent=self.name, type="callback", data=result)
                return
        
        # 2. 子类核心逻辑
        async for event in self._run_impl(ctx):
            yield event
        
        # 3. 运行后回调
        if self.after_agent_callback:
            result = await self.after_agent_callback(ctx)
            if result is not None:
                yield Event(agent=self.name, type="callback", data=result)
    
    @abstractmethod
    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator["Event", None]:
        """核心逻辑 — 子类必须实现"""
        raise NotImplementedError
```

**设计亮点**：
- `run()` 是 final 的模板方法（借鉴 Google），保证回调链的统一执行
- 使用 Pydantic BaseModel，天然支持配置驱动和序列化
- 树结构支持复杂编排

### 4.2 LLM Agent（核心 Agent）

**设计取舍**：融合 OpenAI 的声明式配置风格和 Google 的丰富回调体系。

```python
from typing import Union, Callable, Any

class Agent(BaseAgent):
    """
    核心 LLM Agent。
    命名为 Agent（而非 LlmAgent），因为这是开发者 99% 情况下使用的类。
    """
    
    # === LLM 配置 ===
    model: Union[str, "BaseLLM"] = ""              # 模型名或实例（空 → 向上继承）
    instructions: Union[str, Callable] = ""         # 系统提示词（支持动态函数）
    
    # === 工具 ===
    tools: list["ToolUnion"] = Field(default_factory=list)        # 工具列表
    skills: list["Skill"] = Field(default_factory=list)           # ⭐ Skill 列表（一等公民）
    
    # === Agent 间协作 ===
    handoffs: list[Union["Agent", "Handoff"]] = Field(default_factory=list)  # 交接目标
    
    # === 输入输出 ===
    input_schema: Optional[type] = None             # 输入格式约束
    output_type: Optional[type] = None              # 结构化输出类型
    
    # === 安全 ===
    input_guardrails: list["InputGuardrail"] = Field(default_factory=list)
    output_guardrails: list["OutputGuardrail"] = Field(default_factory=list)
    permission_policy: Optional["PermissionPolicy"] = None
    
    # === 行为配置 ===
    tool_use_behavior: str = "run_llm_again"        # 工具调用后的行为
    max_tool_rounds: int = 20                        # 单次运行最大工具调用轮次
    
    # === 精细回调（借鉴 Google）===
    before_model_callback: Optional[Callable] = None
    after_model_callback: Optional[Callable] = None
    before_tool_callback: Optional[Callable] = None
    after_tool_callback: Optional[Callable] = None
    on_error_callback: Optional[Callable] = None
    
    # ===== 核心方法 =====
    
    async def get_instructions(self, ctx: "RunContext") -> str:
        """获取系统提示词（支持动态生成，借鉴 OpenAI）"""
        if callable(self.instructions):
            result = self.instructions(ctx, self)
            if inspect.isawaitable(result):
                return await result
            return result
        return self.instructions
    
    async def get_all_tools(self, ctx: "RunContext") -> list["BaseTool"]:
        """
        汇总所有可用工具：
        1. 直接配置的 tools（函数/Tool/Toolset 统一处理）
        2. Skills 通过 SkillToolset 转化的工具
        3. Handoff 自动生成的 transfer_to_xxx 工具
        """
        all_tools = []
        
        # 1. 处理 tools（借鉴 Google 的统一化）
        for tool_union in self.tools:
            if callable(tool_union) and not isinstance(tool_union, BaseTool):
                all_tools.append(FunctionTool.from_function(tool_union))
            elif isinstance(tool_union, BaseToolset):
                all_tools.extend(await tool_union.get_tools(ctx))
            else:
                all_tools.append(tool_union)
        
        # 2. 处理 skills（⭐ 核心创新 — Skill 自动桥接为工具）
        if self.skills:
            skill_toolset = SkillToolset(skills=self.skills)
            all_tools.extend(await skill_toolset.get_tools(ctx))
        
        # 3. 处理 handoffs（借鉴 OpenAI）
        for handoff_target in self.handoffs:
            all_tools.append(self._handoff_as_tool(handoff_target))
        
        return all_tools
    
    def as_tool(self, name: str, description: str, **kwargs) -> "FunctionTool":
        """
        把自己变成一个工具，供其他 Agent 调用。
        借鉴 OpenAI 的 as_tool 设计。
        """
        async def _invoke(ctx: "ToolContext", input: str) -> Any:
            result = await Runner.run(self, input=input, context=ctx.shared_context)
            return result.final_output
        
        return FunctionTool(name=name, description=description, handler=_invoke)
    
    async def _run_impl(self, ctx: "RunContext") -> AsyncGenerator["Event", None]:
        """LLM Agent 的核心执行循环"""
        round_count = 0
        
        while round_count < self.max_tool_rounds:
            round_count += 1
            
            # 1. 获取指令和工具
            instructions = await self.get_instructions(ctx)
            tools = await self.get_all_tools(ctx)
            
            # 2. before_model 回调
            if self.before_model_callback:
                override = await self.before_model_callback(ctx, instructions, tools)
                if override is not None:
                    yield Event(agent=self.name, type="model_override", data=override)
                    return
            
            # 3. 调用 LLM
            llm = self._resolve_model()
            response = await llm.generate(
                system=instructions,
                messages=ctx.get_messages(),
                tools=[t.to_schema() for t in tools],
                output_schema=self.output_type,
            )
            
            # 4. after_model 回调
            if self.after_model_callback:
                response = await self.after_model_callback(ctx, response) or response
            
            yield Event(agent=self.name, type="llm_response", data=response)
            
            # 5. 分析响应
            if response.has_tool_calls:
                # 执行工具调用
                for tool_call in response.tool_calls:
                    tool = self._find_tool(tools, tool_call.name)
                    
                    # before_tool 回调
                    if self.before_tool_callback:
                        override = await self.before_tool_callback(ctx, tool, tool_call)
                        if override is not None:
                            yield Event(agent=self.name, type="tool_override", data=override)
                            continue
                    
                    # 权限检查
                    if self.permission_policy:
                        allowed = await self.permission_policy.check(tool, tool_call)
                        if not allowed:
                            yield Event(agent=self.name, type="permission_denied", 
                                       data={"tool": tool_call.name})
                            continue
                    
                    # 执行
                    result = await tool.execute(ctx, tool_call.arguments)
                    
                    # after_tool 回调
                    if self.after_tool_callback:
                        result = await self.after_tool_callback(ctx, tool, result) or result
                    
                    yield Event(agent=self.name, type="tool_result", data=result)
                    ctx.add_tool_result(tool_call.id, result)
                
                # 根据 tool_use_behavior 决定下一步
                if self.tool_use_behavior == "stop":
                    return
                continue  # run_llm_again
            
            elif response.has_handoff:
                yield Event(agent=self.name, type="handoff", 
                           data={"target": response.handoff_target})
                return
            
            else:
                # 最终输出
                yield Event(agent=self.name, type="final_output", data=response.content)
                return
    
    def _resolve_model(self) -> "BaseLLM":
        """模型解析：支持继承（借鉴 Google）"""
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
```

**关键设计决策说明**：

1. **`skills` 作为一等属性**：不像 Google 那样把 SkillToolset 手动放在 tools 里，也不像 OpenAI 那样完全没有 Skill。`skills` 和 `tools` 并列，各有各的语义——tools 是直接可执行的能力，skills 是打包好的专业领域知识。

2. **`instructions` 支持动态函数**：借鉴 OpenAI，instructions 可以是字符串或函数，实现上下文感知的提示词。

3. **`as_tool()` 方法**：借鉴 OpenAI，让 Agent 可以被其他 Agent 当工具使用，实现"委派"模式。

4. **模型继承机制**：借鉴 Google，子 Agent 不设模型时自动继承父 Agent 的模型。

### 4.3 编排 Agent（Orchestrator）

```python
class SequentialAgent(BaseAgent):
    """按顺序执行子 Agent"""
    
    async def _run_impl(self, ctx):
        for sub in self.sub_agents:
            async for event in sub.run(ctx):
                yield event
                if event.type == "escalate":
                    return

class ParallelAgent(BaseAgent):
    """并行执行子 Agent（借鉴 Google 的分支隔离设计）"""
    
    async def _run_impl(self, ctx):
        import asyncio
        tasks = []
        for sub in self.sub_agents:
            branch_ctx = ctx.create_branch(sub.name)  # 隔离上下文
            tasks.append(self._collect_events(sub, branch_ctx))
        
        results = await asyncio.gather(*tasks)
        for events in results:
            for event in events:
                yield event

class LoopAgent(BaseAgent):
    """循环执行子 Agent，直到 escalate 或达到上限"""
    
    max_iterations: int = 10
    
    async def _run_impl(self, ctx):
        for i in range(self.max_iterations):
            for sub in self.sub_agents:
                async for event in sub.run(ctx):
                    yield event
                    if event.type == "escalate":
                        return
```

### 4.4 Agent 间协作：Handoff + as_tool 双模式

这是本架构的重要设计——**同时支持两种 Agent 协作模式**（借鉴 OpenAI 的洞见）：

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  模式一：Handoff（转介）                                          │
│  ─────────────────                                               │
│  Agent A 把整个对话历史交给 Agent B，B 接管控制权。                │
│  类比：把患者从急诊科转到专科。                                    │
│                                                                  │
│  Agent A ──[transfer_to_B]──→ Agent B（带着完整对话历史）          │
│                                                                  │
│  模式二：as_tool（委派）                                          │
│  ───────────────                                                 │
│  Agent A 把 Agent B 当工具调用，B 只收到具体任务输入，             │
│  完成后结果返回给 A，A 继续工作。                                  │
│  类比：打电话咨询专家一个问题，然后自己继续干活。                   │
│                                                                  │
│  Agent A ──[call B.as_tool()]──→ Agent B ──[result]──→ Agent A    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

```python
@dataclass
class Handoff:
    """Agent 间的控制权转移"""
    target: Agent                          # 交接目标
    tool_name: Optional[str] = None        # 在 LLM 视角的工具名（默认 transfer_to_xxx）
    tool_description: Optional[str] = None # 描述
    input_filter: Optional[Callable] = None  # 输入过滤（可裁剪对话历史）
    
    def to_tool(self) -> "FunctionTool":
        """将 handoff 转化为 LLM 可调用的工具"""
        name = self.tool_name or f"transfer_to_{self.target.name}"
        desc = self.tool_description or f"将对话交给{self.target.description}"
        
        async def _invoke(ctx, args):
            return HandoffSignal(target=self.target, args=args)
        
        return FunctionTool(name=name, description=desc, handler=_invoke)
```

---

## 五、Tool 层设计

### 5.1 统一工具类型体系

```python
# 三种工具输入形态，框架自动统一处理
ToolUnion = Union[
    Callable,       # 普通 Python 函数 → 自动包装为 FunctionTool
    "BaseTool",     # Tool 对象
    "BaseToolset",  # 工具集（如 SkillToolset、MCPToolset）
]

class BaseTool(BaseModel):
    """工具基类"""
    name: str
    description: str
    
    @abstractmethod
    async def execute(self, ctx: "ToolContext", arguments: dict) -> Any: ...
    
    @abstractmethod
    def to_schema(self) -> dict:
        """生成 JSON Schema（供 LLM 理解参数格式）"""
        ...

class BaseToolset(BaseModel):
    """工具集基类 — 可动态展开为多个 Tool"""
    
    @abstractmethod
    async def get_tools(self, ctx: "RunContext") -> list[BaseTool]: ...
```

### 5.2 @function_tool 装饰器

**借鉴 OpenAI 的极简设计**，一行代码把函数变工具：

```python
def function_tool(func=None, *, name=None, description=None, 
                  needs_approval=False, timeout=None):
    """
    装饰器：将 Python 函数自动转换为 FunctionTool。
    
    自动完成：
    1. 从函数签名推断参数 JSON Schema
    2. 从 docstring 提取工具描述
    3. 用 Pydantic 验证 LLM 传入的参数
    """
    def decorator(fn):
        schema = generate_function_schema(fn, name_override=name, desc_override=description)
        
        async def _invoke(ctx: ToolContext, raw_args: str) -> Any:
            parsed = json.loads(raw_args)
            validated = schema.pydantic_model(**parsed)
            args, kwargs = schema.to_call_args(validated)
            
            # 支持带上下文的工具函数
            if schema.takes_context:
                return await fn(ctx, *args, **kwargs)
            return await fn(*args, **kwargs)
        
        return FunctionTool(
            name=schema.name,
            description=schema.description,
            json_schema=schema.json_schema,
            handler=_invoke,
            needs_approval=needs_approval,
            timeout_seconds=timeout,
        )
    
    return decorator(func) if callable(func) else decorator
```

**使用示例**：

```python
@function_tool
async def search_documents(query: str, top_k: int = 5) -> list[str]:
    """在知识库中搜索相关文档
    
    Args:
        query: 搜索关键词
        top_k: 返回结果数量
    """
    return await kb.search(query, top_k)

@function_tool(needs_approval=True, timeout=30)
async def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件（需要人工确认）"""
    return await email_service.send(to, subject, body)
```

### 5.3 MCP 集成

```python
class MCPToolset(BaseToolset):
    """MCP 工具集 — 连接外部 MCP 服务器"""
    
    server_uri: str               # MCP 服务器地址
    allowed_tools: Optional[list[str]] = None  # 工具白名单
    
    async def get_tools(self, ctx) -> list[BaseTool]:
        """连接 MCP 服务器，获取所有可用工具"""
        async with MCPClient(self.server_uri) as client:
            remote_tools = await client.list_tools()
            return [MCPTool(server=client, tool_def=t) for t in remote_tools
                    if not self.allowed_tools or t.name in self.allowed_tools]
```

---

## 六、Skill 层设计（核心创新）

### 6.1 Skill 定位与结构标准

**Skill 是什么？** Skill 是**指令 + 资源 + 脚本的打包体**，代表一个特定领域的专业知识和工具集合。

**Skill 与 Tool 的区别**：

| 维度 | Tool | Skill |
|------|------|-------|
| **本质** | 一个可执行的函数 | 一个领域知识包 |
| **复杂度** | 单一功能 | 包含指令、参考文档、脚本、资源 |
| **加载方式** | 全量在内存中 | 三级渐进式加载 |
| **使用方式** | LLM 直接调用 | LLM 先读指令，按步骤执行 |
| **类比** | 一把螺丝刀 | 一本维修手册（含工具清单） |

**Skill 文件夹标准**（兼容 agentskills.io 规范）：

```
my-skill/
├── SKILL.md              # 【必须】身份证 + 说明书
│                         #   - YAML Frontmatter: name, description, metadata
│                         #   - Markdown Body: 详细指令
├── references/           # 【可选】参考文档（LLM 按需读取）
│   ├── api_doc.md
│   └── examples.md
├── assets/               # 【可选】资源文件（模板、Schema 等）
│   └── template.json
├── scripts/              # 【可选】可执行脚本
│   └── process_data.py
└── LICENSE               # 【可选】许可证
```

### 6.2 三级渐进式加载（L1/L2/L3）

这是 Skill 系统最精妙的设计，**直接采用 Google ADK 的三级模型**，同时借鉴 Anthropic 的触发机制：

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Level 1 — 发现层（Always in Context）                              │
│  ─────────────────────────────────                                  │
│  内容：name + description（来自 SKILL.md 的 YAML Frontmatter）       │
│  大小：~100 词 / Skill                                              │
│  加载时机：Agent 启动时，自动注入到 LLM 的系统提示词中               │
│  作用：让 LLM 知道"有哪些 Skill 可用"                               │
│                                                                     │
│  例：<skill name="pdf-processor" desc="处理PDF文件：合并、拆分..."/> │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Level 2 — 指令层（On-Demand）                                      │
│  ─────────────────────────                                          │
│  内容：SKILL.md 的 Markdown 正文（详细工作流指令）                    │
│  大小：建议 <500 行                                                  │
│  加载时机：LLM 判断需要使用某个 Skill 后，调用 load_skill 工具       │
│  作用：告诉 LLM "具体怎么做"                                        │
│                                                                     │
│  例："Step 1: 读取 references/format_rules.md                       │
│       Step 2: 运行 scripts/merge_pdf.py --files ..."                │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Level 3 — 资源层（On-Demand）                                      │
│  ─────────────────────────                                          │
│  内容：references/、assets/、scripts/ 目录下的具体文件               │
│  大小：不限                                                          │
│  加载时机：L2 指令要求时，调用 load_skill_resource / run_script      │
│  作用：提供具体的参考资料，或执行脚本完成实际操作                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**为什么采用三级加载？**

假设一个 Agent 配置了 10 个 Skill，每个 Skill 的完整内容 ~5000 token：
- **不分级**：启动时就加载 50,000 token 到上下文 → 极大浪费
- **三级加载**：启动时只加载 10 × 100 = 1,000 token（L1），只在需要时才加载某个 Skill 的 L2（~2000 token）和 L3（按需）

### 6.3 Skill 数据模型

```python
from pydantic import BaseModel, field_validator
import re

class SkillFrontmatter(BaseModel):
    """L1：Skill 元数据"""
    name: str                                    # kebab-case 标识符
    description: str                             # 触发描述（<1024 字符）
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if not re.match(r'^[a-z][a-z0-9-]{0,63}$', v):
            raise ValueError("name 必须是 kebab-case，长度不超过 64")
        return v
    
    @field_validator("description")
    @classmethod 
    def validate_description(cls, v):
        if len(v) > 1024:
            raise ValueError("description 不超过 1024 字符")
        return v

class SkillScript(BaseModel):
    """脚本包装器"""
    filename: str
    source: str
    language: str = "python"  # python / shell
    
    def __str__(self) -> str:
        return self.source

class SkillResources(BaseModel):
    """L3：Skill 资源"""
    references: dict[str, Union[str, bytes]] = Field(default_factory=dict)
    assets: dict[str, Union[str, bytes]] = Field(default_factory=dict)
    scripts: dict[str, SkillScript] = Field(default_factory=dict)
    
    def get_reference(self, name: str) -> Optional[Union[str, bytes]]:
        return self.references.get(name)
    
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
    frontmatter: SkillFrontmatter                # L1：元数据
    instructions: str                             # L2：详细指令（SKILL.md 正文）
    resources: SkillResources = SkillResources()  # L3：附加资源
    
    @property
    def name(self) -> str:
        return self.frontmatter.name
    
    @property
    def description(self) -> str:
        return self.frontmatter.description
    
    @property
    def additional_tools(self) -> list[str]:
        """Skill 声明需要的额外工具"""
        return self.frontmatter.metadata.get("additional_tools", [])
```

### 6.4 SkillRegistry — Skill 的注册与发现

```python
class SkillRegistry:
    """
    Skill 注册中心 — 管理 Skill 的发现、加载、缓存。
    
    支持多种来源：
    1. 本地目录
    2. 代码中直接构造
    3. 远程仓库（可扩展）
    """
    
    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._search_paths: list[Path] = []
    
    def register(self, skill: Skill):
        """直接注册一个 Skill"""
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' 已注册")
        self._skills[skill.name] = skill
    
    def add_search_path(self, path: Union[str, Path]):
        """添加 Skill 搜索路径"""
        self._search_paths.append(Path(path))
    
    def discover(self) -> list[Skill]:
        """从搜索路径中自动发现并加载所有 Skill"""
        for search_path in self._search_paths:
            for skill_dir in search_path.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skill = load_skill_from_dir(skill_dir)
                    self.register(skill)
        return list(self._skills.values())
    
    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
    
    def list_all(self) -> list[SkillFrontmatter]:
        """返回所有 Skill 的 L1 信息"""
        return [s.frontmatter for s in self._skills.values()]


def load_skill_from_dir(skill_dir: Path) -> Skill:
    """从目录加载 Skill（借鉴 Google ADK 的加载逻辑）"""
    skill_md_path = skill_dir / "SKILL.md"
    content = skill_md_path.read_text(encoding="utf-8")
    
    # 解析 YAML Frontmatter
    if not content.startswith("---"):
        raise ValueError("SKILL.md 必须以 --- 开头的 YAML Frontmatter 开始")
    
    _, frontmatter_yaml, body = content.split("---", 2)
    parsed = yaml.safe_load(frontmatter_yaml)
    frontmatter = SkillFrontmatter.model_validate(parsed)
    
    # 验证目录名与 Skill 名一致
    if skill_dir.name != frontmatter.name:
        raise ValueError(f"Skill 名 '{frontmatter.name}' 与目录名 '{skill_dir.name}' 不一致")
    
    # 加载资源
    references = _load_dir_files(skill_dir / "references")
    assets = _load_dir_files(skill_dir / "assets")
    raw_scripts = _load_dir_files(skill_dir / "scripts")
    scripts = {
        name: SkillScript(filename=name, source=src, language=_detect_lang(name))
        for name, src in raw_scripts.items()
    }
    
    return Skill(
        frontmatter=frontmatter,
        instructions=body.strip(),
        resources=SkillResources(references=references, assets=assets, scripts=scripts),
    )
```

### 6.5 SkillToolset — Skill 到工具的桥接

**这是 Skill 系统的核心枢纽**，负责把 Skill 转化为 LLM 可调用的标准工具：

```python
class SkillToolset(BaseToolset):
    """
    Skill → Tool 桥接器。
    
    核心思想（借鉴 Google ADK）：
    把 Skill 体系暴露为 4 个标准工具，让 LLM 通过 function calling 自主使用 Skill。
    
    同时融合 Anthropic 的 description 驱动触发思想：
    通过 process_llm_request 自动注入 Skill 列表到系统提示词。
    """
    
    def __init__(self, skills: list[Skill], additional_tools: list = None,
                 code_executor: "BaseCodeExecutor" = None):
        self._skills = {s.name: s for s in skills}
        self._additional_tools = {t.name: t for t in (additional_tools or [])}
        self._code_executor = code_executor
        self._activated_skills: set[str] = set()
    
    async def get_tools(self, ctx: "RunContext") -> list[BaseTool]:
        """返回 4 个桥接工具 + 动态注入的额外工具"""
        base_tools = [
            self._make_list_skills_tool(),
            self._make_load_skill_tool(),
            self._make_load_resource_tool(),
            self._make_run_script_tool(),
        ]
        
        # 动态工具注入
        dynamic_tools = self._get_additional_tools_for_activated_skills()
        
        return base_tools + dynamic_tools
    
    # ===== 四个桥接工具的实现 =====
    
    def _make_list_skills_tool(self) -> FunctionTool:
        """工具 1：list_skills — 列出所有可用 Skill（L1 信息）"""
        
        async def handler(ctx, args):
            skills_xml = "<available_skills>\n"
            for skill in self._skills.values():
                skills_xml += f"  <skill>\n"
                skills_xml += f"    <name>{skill.name}</name>\n"
                skills_xml += f"    <description>{skill.description}</description>\n"
                skills_xml += f"  </skill>\n"
            skills_xml += "</available_skills>"
            return skills_xml
        
        return FunctionTool(
            name="list_skills",
            description="列出所有可用的专业技能（Skill）",
            handler=handler,
            json_schema={"type": "object", "properties": {}},
        )
    
    def _make_load_skill_tool(self) -> FunctionTool:
        """工具 2：load_skill — 加载 Skill 的 L2 详细指令"""
        
        async def handler(ctx, args):
            name = args.get("skill_name")
            skill = self._skills.get(name)
            if not skill:
                return f"Error: Skill '{name}' not found"
            
            # 标记为已激活
            self._activated_skills.add(name)
            
            return {
                "skill_name": name,
                "instructions": skill.instructions,
                "available_resources": skill.resources.list_all(),
            }
        
        return FunctionTool(
            name="load_skill",
            description="加载指定 Skill 的详细操作指令。使用前必须先加载。",
            handler=handler,
            json_schema={
                "type": "object",
                "properties": {"skill_name": {"type": "string", "description": "Skill名称"}},
                "required": ["skill_name"]
            },
        )
    
    def _make_load_resource_tool(self) -> FunctionTool:
        """工具 3：load_skill_resource — 加载 Skill 的 L3 资源"""
        
        async def handler(ctx, args):
            skill_name = args["skill_name"]
            resource_path = args["path"]  # 如 "references/api_doc.md"
            
            skill = self._skills.get(skill_name)
            if not skill:
                return f"Error: Skill '{skill_name}' not found"
            
            parts = resource_path.split("/", 1)
            category, filename = parts[0], parts[1] if len(parts) > 1 else ""
            
            if category == "references":
                content = skill.resources.get_reference(filename)
            elif category == "assets":
                content = skill.resources.assets.get(filename)
            elif category == "scripts":
                script = skill.resources.get_script(filename)
                content = script.source if script else None
            else:
                return f"Error: 未知资源类型 '{category}'"
            
            if content is None:
                return f"Error: 资源 '{resource_path}' 不存在"
            
            return {"skill_name": skill_name, "path": resource_path, "content": content}
        
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
                "required": ["skill_name", "path"]
            },
        )
    
    def _make_run_script_tool(self) -> FunctionTool:
        """工具 4：run_skill_script — 执行 Skill 的脚本"""
        
        async def handler(ctx, args):
            skill_name = args["skill_name"]
            script_path = args["script_name"]
            script_args = args.get("arguments", {})
            
            skill = self._skills.get(skill_name)
            script = skill.resources.get_script(script_path)
            
            if not script:
                return f"Error: 脚本 '{script_path}' 不存在"
            
            # 在沙箱中执行脚本（借鉴 Google 的临时目录方案）
            executor = self._code_executor or DefaultSandboxExecutor()
            result = await executor.run(
                skill=skill,
                script=script,
                arguments=script_args,
            )
            return result
        
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
                "required": ["skill_name", "script_name"]
            },
        )
    
    # ===== 自动注入 Skill 列表到 LLM 请求 =====
    
    def get_system_prompt_injection(self) -> str:
        """
        生成要注入到 LLM 系统提示词中的 Skill 说明。
        这确保了 LLM 在每次调用时都知道有哪些 Skill 可用。
        """
        skills_xml = "<available_skills>\n"
        for skill in self._skills.values():
            skills_xml += f"<skill>\n"
            skills_xml += f"  <name>{skill.name}</name>\n"
            skills_xml += f"  <description>{skill.description}</description>\n"
            skills_xml += f"</skill>\n"
        skills_xml += "</available_skills>\n"
        
        return f"""
你可以使用专业技能（Skill）来完成复杂任务。

{skills_xml}

使用规则：
1. 如果某个 Skill 与用户请求相关，先调用 `load_skill` 加载其详细指令
2. 加载后，严格按照指令步骤执行
3. 需要参考资料时，使用 `load_skill_resource` 按需加载
4. 需要执行脚本时，使用 `run_skill_script`
5. 不要凭猜测使用 Skill，先加载指令再行动
"""

    # ===== 动态工具注入 =====
    
    def _get_additional_tools_for_activated_skills(self) -> list[BaseTool]:
        """Skill 被激活后，动态暴露其声明的额外工具（借鉴 Google 的 adk_additional_tools）"""
        tools = []
        for skill_name in self._activated_skills:
            skill = self._skills.get(skill_name)
            if skill:
                for tool_name in skill.additional_tools:
                    if tool_name in self._additional_tools:
                        tools.append(self._additional_tools[tool_name])
        return tools
```

### 6.6 Skill 的动态工具注入

**这个设计借鉴了 Google ADK 的 `adk_additional_tools` 机制**，解决了一个实际问题：某些 Skill 需要 Agent 拥有特定的工具能力，但这些工具只在 Skill 被使用时才需要暴露给 LLM。

```yaml
# SKILL.md 中声明额外工具需求
---
name: data-analysis
description: 数据分析技能，支持 CSV/Excel 数据的统计分析和可视化
metadata:
  additional_tools:
    - read_csv          # 只在该 Skill 被激活后才暴露给 LLM
    - plot_chart
---
```

**触发流程**：

```
1. Agent 启动 → SkillToolset 只暴露 4 个基础工具
2. LLM 调用 load_skill("data-analysis") → Skill 被激活
3. 下一轮 LLM 调用 → SkillToolset.get_tools() 额外返回 read_csv、plot_chart
4. LLM 现在可以使用这些工具了
```

---

## 七、Runner 层设计

### 7.1 Runner 核心循环

**借鉴 OpenAI 的 turn-based 执行模型**，同时融入 Google 的 Event 流式输出：

```python
class Runner:
    """
    Agent 运行引擎。
    驱动 Agent 的 turn-by-turn 执行循环，处理工具调用和 Agent 切换。
    """
    
    @classmethod
    async def run(cls, agent: Agent, *, input: str, 
                  context: Any = None, max_turns: int = 10) -> "RunResult":
        """异步运行 Agent"""
        ctx = RunContext(
            root_agent=agent,
            current_agent=agent,
            input=input,
            shared_context=context,
        )
        
        current_agent = agent
        events = []
        
        for turn in range(max_turns):
            # 运行输入护栏
            if current_agent.input_guardrails:
                for guardrail in current_agent.input_guardrails:
                    result = await guardrail.check(ctx)
                    if result.triggered:
                        return RunResult(
                            final_output=None,
                            error=f"输入被安全护栏拦截: {result.reason}",
                            events=events,
                        )
            
            # 执行当前 Agent
            async for event in current_agent.run(ctx):
                events.append(event)
                
                if event.type == "final_output":
                    # 运行输出护栏
                    if current_agent.output_guardrails:
                        for guardrail in current_agent.output_guardrails:
                            result = await guardrail.check(ctx, event.data)
                            if result.triggered:
                                return RunResult(
                                    final_output=None,
                                    error=f"输出被安全护栏拦截: {result.reason}",
                                    events=events,
                                )
                    
                    return RunResult(
                        final_output=event.data,
                        events=events,
                        last_agent=current_agent,
                    )
                
                elif event.type == "handoff":
                    # 切换 Agent
                    target_name = event.data["target"]
                    current_agent = cls._find_agent(agent, target_name)
                    break  # 进入下一个 turn
        
        raise MaxTurnsExceeded(f"超过最大轮次 {max_turns}")
    
    @classmethod
    def run_sync(cls, agent, **kwargs) -> "RunResult":
        """同步运行（便利方法）"""
        import asyncio
        return asyncio.run(cls.run(agent, **kwargs))
    
    @classmethod
    async def run_streamed(cls, agent, **kwargs) -> AsyncGenerator["Event", None]:
        """流式运行，实时产出 Event"""
        ctx = RunContext(...)
        async for event in agent.run(ctx):
            yield event
```

### 7.2 RunContext — 运行上下文

```python
@dataclass
class RunContext:
    """一次运行的完整上下文"""
    
    root_agent: BaseAgent          # 根 Agent
    current_agent: BaseAgent       # 当前执行的 Agent
    input: str                     # 用户输入
    shared_context: Any = None     # 共享上下文（用户自定义数据）
    
    # === 会话管理 ===
    session_id: str = field(default_factory=lambda: str(uuid4()))
    messages: list = field(default_factory=list)
    state: dict = field(default_factory=dict)
    
    # === 分支支持（并行 Agent 用）===
    branch: Optional[str] = None
    
    def add_message(self, role: str, content: Any):
        self.messages.append({"role": role, "content": content})
    
    def add_tool_result(self, tool_call_id: str, result: Any):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(result),
        })
    
    def get_messages(self) -> list:
        return self.messages
    
    def create_branch(self, branch_name: str) -> "RunContext":
        """创建隔离的分支上下文（并行 Agent 用）"""
        branch_ctx = copy.deepcopy(self)
        branch_ctx.branch = branch_name
        return branch_ctx
```

### 7.3 Event 流式输出

```python
@dataclass
class Event:
    """运行过程中产生的事件"""
    agent: str                      # 产生事件的 Agent 名称
    type: str                       # 事件类型
    data: Any = None                # 事件数据
    timestamp: float = field(default_factory=time.time)
    
    # 事件类型枚举：
    # - "llm_response"    LLM 返回了响应
    # - "tool_call"       准备调用工具
    # - "tool_result"     工具执行结果
    # - "handoff"         Agent 交接
    # - "final_output"    最终输出
    # - "escalate"        上报/退出信号
    # - "callback"        回调产生的事件
    # - "error"           错误
    # - "permission_denied" 权限拒绝

@dataclass
class RunResult:
    """运行最终结果"""
    final_output: Any                          # 最终输出
    events: list[Event] = field(default_factory=list)  # 所有事件
    last_agent: Optional[BaseAgent] = None     # 最后执行的 Agent
    error: Optional[str] = None                # 错误信息
    
    @property
    def success(self) -> bool:
        return self.error is None and self.final_output is not None
```

---

## 八、回调与安全机制

### 8.1 生命周期回调链

**综合 Google 的精细回调和 Anthropic 的 Hook 机制**，定义 6 个回调点：

```
                    ┌─────────────────────────┐
                    │     用户消息进入          │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
               ❶   │  before_agent_callback   │  ← 可跳过整个 Agent
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
               ❷   │  before_model_callback   │  ← 可修改/替代 LLM 请求
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     调用 LLM 模型        │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
               ❸   │  after_model_callback    │  ← 可修改 LLM 响应
                    └────────────┬────────────┘
                                 │
                         ┌───────┴────────┐
                         │  有工具调用？    │
                         └───┬─────────┬──┘
                          是 │         │ 否
                    ┌────────▼───┐     │
               ❹   │ before_tool │     │  ← 可拦截/修改工具调用
                    │  _callback │     │
                    └────────┬───┘     │
                    ┌────────▼───┐     │
                    │  执行工具   │     │
                    └────────┬───┘     │
                    ┌────────▼───┐     │
               ❺   │ after_tool  │     │  ← 可修改工具结果
                    │  _callback │     │
                    └────────┬───┘     │
                             │         │
                             └────┬────┘
                    ┌─────────────▼───────────┐
               ❻   │  after_agent_callback    │  ← 可追加额外回复
                    └─────────────────────────┘
```

### 8.2 Guardrail 安全护栏

**借鉴 OpenAI 的 Input/Output 双向护栏设计**：

```python
@dataclass
class GuardrailResult:
    triggered: bool = False         # 是否触发熔断
    reason: Optional[str] = None    # 触发原因
    info: dict = field(default_factory=dict)  # 附加信息

class InputGuardrail:
    """输入安全护栏 — Agent 运行前检查"""
    
    def __init__(self, check_fn: Callable, *, name: str = None, parallel: bool = True):
        self.check_fn = check_fn
        self.name = name or check_fn.__name__
        self.parallel = parallel   # 是否与 Agent 并行运行
    
    async def check(self, ctx: RunContext) -> GuardrailResult:
        result = self.check_fn(ctx)
        if inspect.isawaitable(result):
            result = await result
        return result

class OutputGuardrail:
    """输出安全护栏 — Agent 产生输出后检查"""
    
    def __init__(self, check_fn: Callable, *, name: str = None):
        self.check_fn = check_fn
        self.name = name or check_fn.__name__
    
    async def check(self, ctx: RunContext, output: Any) -> GuardrailResult:
        result = self.check_fn(ctx, output)
        if inspect.isawaitable(result):
            result = await result
        return result

# 便捷装饰器
def input_guardrail(fn):
    return InputGuardrail(fn)

def output_guardrail(fn):
    return OutputGuardrail(fn)
```

### 8.3 权限控制

**借鉴 Anthropic 的三层权限模型**：

```python
class PermissionPolicy:
    """
    工具权限控制策略。
    三种粒度：预设模式 > 白名单 > 自定义回调
    """
    
    mode: str = "ask"               # "allow_all" / "deny_all" / "ask"
    allowed_tools: set[str] = set() # 工具白名单
    custom_check: Optional[Callable] = None  # 自定义检查函数
    
    async def check(self, tool: BaseTool, call: "ToolCall") -> bool:
        if self.mode == "allow_all":
            return True
        if self.mode == "deny_all":
            return False
        
        # 白名单检查
        if tool.name in self.allowed_tools:
            return True
        
        # 自定义回调
        if self.custom_check:
            result = self.custom_check(tool.name, call.arguments)
            if inspect.isawaitable(result):
                result = await result
            return result
        
        return False  # 默认拒绝
```

---

## 九、完整使用示例

### 示例 1：最简单的 Agent

```python
from myframework import Agent, Runner

agent = Agent(
    name="assistant",
    instructions="你是一个有帮助的中文助手。",
    model="gpt-4o",
)

result = Runner.run_sync(agent, input="什么是量子计算？")
print(result.final_output)
```

### 示例 2：带工具的 Agent

```python
from myframework import Agent, Runner, function_tool

@function_tool
async def search_web(query: str) -> str:
    """搜索互联网获取最新信息"""
    return await web_search_api(query)

@function_tool(needs_approval=True)
async def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件（需人工确认）"""
    return await email_api.send(to, subject, body)

agent = Agent(
    name="research_assistant",
    instructions="你是一个研究助手，可以搜索网络和发送邮件。",
    model="gpt-4o",
    tools=[search_web, send_email],
)

result = await Runner.run(agent, input="帮我查一下最新的AI论文并发邮件给老板")
```

### 示例 3：带 Skill 的 Agent

```python
from myframework import Agent, Runner, Skill, SkillFrontmatter, SkillResources, load_skill_from_dir

# 方式一：从目录加载 Skill
pdf_skill = load_skill_from_dir("./skills/pdf-processor")

# 方式二：代码中直接定义 Skill
greeting_skill = Skill(
    frontmatter=SkillFrontmatter(
        name="greeting-skill",
        description="一个友好的问候技能，适合迎接新用户",
        metadata={"additional_tools": ["get_user_timezone"]},
    ),
    instructions="""
## 使用步骤

1. 读取 references/greeting_templates.md 获取问候模板
2. 根据用户语言和时区选择合适的模板
3. 如果需要时区信息，使用 get_user_timezone 工具
4. 返回个性化的问候语
""",
    resources=SkillResources(
        references={"greeting_templates.md": "# 问候模板\n- 早上好！{name}\n- ..."}
    ),
)

# 创建带 Skill 的 Agent
agent = Agent(
    name="smart_assistant",
    instructions="你是一个智能助手，可以使用专业技能来完成任务。",
    model="gpt-4o",
    skills=[pdf_skill, greeting_skill],   # ⭐ Skill 作为一等公民
    tools=[get_user_timezone],             # 常规工具
)

result = await Runner.run(agent, input="帮我合并这三个 PDF 文件")
```

### 示例 4：多 Agent 协作

```python
# Agent 间交接（Handoff 模式）
researcher = Agent(
    name="researcher", 
    instructions="你是一个研究分析师",
    tools=[search_web, search_papers],
)

writer = Agent(
    name="writer",
    instructions="你是一个技术作家",
    tools=[format_markdown],
)

coordinator = Agent(
    name="coordinator",
    instructions="你负责协调研究和写作任务",
    handoffs=[researcher, writer],  # 可以交接给他们
)

# Agent 当工具使用（as_tool 模式）
data_analyst = Agent(
    name="analyst",
    instructions="你是数据分析专家",
    tools=[query_database, plot_chart],
)

manager = Agent(
    name="project_manager",
    instructions="你是项目经理，需要分析数据时调用分析师",
    tools=[
        data_analyst.as_tool(
            name="analyze_data",
            description="调用数据分析师进行数据分析"
        ),
    ],
)
```

### 示例 5：带安全护栏的 Agent

```python
@input_guardrail
async def check_sensitive_content(ctx):
    """检查输入是否包含敏感内容"""
    # 可以调用另一个 LLM 来分类
    is_sensitive = await classify_content(ctx.input)
    return GuardrailResult(triggered=is_sensitive, reason="检测到敏感内容")

@output_guardrail
async def check_factual_accuracy(ctx, output):
    """检查输出是否存在事实错误"""
    has_errors = await fact_check(output)
    return GuardrailResult(triggered=has_errors, reason="输出可能存在事实错误")

agent = Agent(
    name="safe_assistant",
    instructions="你是一个负责任的助手",
    input_guardrails=[check_sensitive_content],
    output_guardrails=[check_factual_accuracy],
    permission_policy=PermissionPolicy(
        mode="ask",
        allowed_tools={"search_web", "read_file"},
    ),
)
```

### 示例 6：编排模式

```python
# 顺序执行：提取 → 分析 → 生成报告
pipeline = SequentialAgent(
    name="report_pipeline",
    sub_agents=[
        Agent(name="extractor", instructions="从文档中提取关键数据..."),
        Agent(name="analyzer", instructions="分析提取的数据..."),
        Agent(name="reporter", instructions="生成最终报告..."),
    ],
)

# 并行执行：同时分析多个维度
parallel_analysis = ParallelAgent(
    name="multi_analysis",
    sub_agents=[
        Agent(name="financial_analyst", instructions="分析财务数据..."),
        Agent(name="market_analyst", instructions="分析市场趋势..."),
        Agent(name="risk_analyst", instructions="分析风险因素..."),
    ],
)

# 循环执行：写代码 → 审查 → 修改 → 再审查...
code_review_loop = LoopAgent(
    name="code_review",
    max_iterations=5,
    sub_agents=[
        Agent(name="coder", instructions="编写或修改代码..."),
        Agent(name="reviewer", instructions="审查代码，如果通过则发送 escalate 信号..."),
    ],
)
```

---

## 十、与三大框架的对比

| 设计维度 | Google ADK | OpenAI Agents SDK | Anthropic Claude SDK | **本方案** |
|---------|-----------|-------------------|---------------------|-----------|
| **Agent 定义** | Pydantic BaseModel 继承 | dataclass | 子进程控制 | **Pydantic BaseModel** |
| **Skill 地位** | 通过 SkillToolset 接入 | 无 Skill 概念 | 文件系统+CLI | **⭐ 一等公民属性** |
| **三级加载** | ✅ 完整实现 | ❌ | ✅ 概念相同 | **✅ 完整实现** |
| **Agent 协作** | 嵌套 sub-agent | Handoff + as_tool | Subagent | **Handoff + as_tool 双模式** |
| **编排 Agent** | Seq/Para/Loop | 无内置 | 无内置 | **Seq/Para/Loop** |
| **工具定义** | FunctionTool + Toolset | @function_tool | @tool + MCP | **@function_tool + Toolset** |
| **安全护栏** | 回调实现 | Guardrail 内置 | Hook + 权限 | **Guardrail + Permission 内置** |
| **回调点** | 6 个 | 2 个 | Hook 事件 | **6 个精细回调** |
| **模型无关** | 较弱(Gemini 优先) | 较弱(OpenAI 优先) | 绑定 Claude | **✅ 完全抽象** |
| **动态工具注入** | ✅ adk_additional_tools | ❌ | ❌ | **✅ Skill 激活后注入** |

### 核心优势总结

1. **Skill 一等公民**：`skills=[...]` 与 `tools=[...]` 并列，语义清晰
2. **双协作模式**：Handoff（转介）+ as_tool（委派），灵活覆盖所有场景
3. **安全内置**：不是可选项，从护栏到权限都是架构级考虑
4. **三级加载**：经过 Google 和 Anthropic 验证的高效策略
5. **回调全覆盖**：6 个回调点，任何环节都可拦截定制
6. **模型无关**：抽象 LLM 接口，不绑定任何厂商

---

## 十一、开放讨论点

以下是设计过程中需要进一步讨论和决策的问题：

### 讨论点 1：Skill 与 Agent 的边界

**现状**：Skill 是"指令 + 资源包"，Agent 是"LLM 配置单元"。Skill 通过 SkillToolset 桥接到 Agent。

**替代方案**：让 Skill 可以直接包含一个 sub-Agent（即 Skill 不仅是知识包，还可以是一个独立的 Agent）。这样一个 Skill 可以有自己的 LLM 配置、独立的对话循环。

**利弊**：
- 优：更强大，Skill 能做更复杂的事
- 弊：概念混淆——Skill 和 Agent 的区别变得模糊

### 讨论点 2：Skill 的版本管理与分发

**需求**：在团队或社区中共享 Skill。

**可选方案**：
- A：Git 仓库（简单粗暴）
- B：类似 npm 的包管理器（`skill install pdf-processor`）
- C：云端 Skill 市场（类似 Anthropic 的 marketplace.json）

### 讨论点 3：Skill 的安全性

**风险**：Skill 中的脚本可能执行危险操作。

**可选方案**：
- A：沙箱执行（Docker / 临时目录 / WASM）
- B：预审批机制（安装时审查脚本内容）
- C：能力声明（Skill 在 frontmatter 中声明需要的系统权限）

### 讨论点 4：多模型支持策略

**需求**：不同的 Agent 可能需要不同的 LLM 提供商。

**当前设计**：通过 `LLMRegistry` 统一注册和创建 LLM 实例。

**待细化**：
- 如何处理不同厂商的 function calling 格式差异？
- 如何统一 token 计费？
- 是否需要 LiteLLM 式的适配层？

### 讨论点 5：状态持久化

**需求**：Agent 的对话历史、Skill 的激活状态需要跨会话保持。

**可选方案**：
- A：内存 + 文件系统（简单场景）
- B：Session Store 抽象（支持 Redis / DB / 文件）
- C：集成外部 Memory 系统（如 Mem0）

---

> **请评审以上架构设计方案。**  
> 欢迎从以下角度提出反馈：
> 1. 整体架构的合理性
> 2. Skill 层设计是否有遗漏
> 3. 安全机制是否充分
> 4. 开放讨论点的倾向
> 5. 其他需要补充的功能模块
