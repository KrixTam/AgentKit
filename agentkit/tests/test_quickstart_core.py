from __future__ import annotations

import asyncio

from pydantic import BaseModel

from agentkit.agents.agent import Agent
from agentkit.agents.base_agent import BaseAgent
from agentkit.agents.orchestrators import LoopAgent, SequentialAgent
from agentkit.runner.context import RunContext
from agentkit.runner.events import Event, EventType
from agentkit.runner.runner import Runner


class EchoAgent(BaseAgent):
    async def _run_impl(self, ctx):
        yield Event(agent=self.name, type=EventType.LLM_RESPONSE, data=f"thinking:{ctx.input}")
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=f"echo:{ctx.input}")


class OnceAgent(BaseAgent):
    async def _run_impl(self, ctx):
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=self.name)


class ModelEchoAgent(Agent):
    async def _run_impl(self, ctx):
        yield Event(agent=self.name, type=EventType.FINAL_OUTPUT, data=f"active_model={self.model}")


class LockedEchoAgent(ModelEchoAgent):
    model: str = "ollama/qwen3.5:cloud"
    model_cosplay_enabled: bool = False


class CosplayEchoAgent(ModelEchoAgent):
    model: str = "ollama/qwen3.5:cloud"
    model_cosplay_enabled: bool = True


class ToolResultSchema(BaseModel):
    tool: str
    result: str


def test_quickstart_runner_sync_async_stream_modes():
    agent = EchoAgent(name="echo")

    sync_result = Runner.run_sync(agent, input="hello")
    assert sync_result.success is True
    assert sync_result.final_output == "echo:hello"

    async def _case():
        async_result = await Runner.run(agent, input="hello")
        assert async_result.success is True
        assert async_result.final_output == "echo:hello"

        streamed_events = [event async for event in Runner.run_streamed(agent, input="hello")]
        assert [e.type for e in streamed_events] == [EventType.LLM_RESPONSE, EventType.FINAL_OUTPUT]
        assert streamed_events[-1].data == "echo:hello"

    asyncio.run(_case())


def test_quickstart_sequential_and_loop_behaviors():
    async def _case():
        seq = SequentialAgent(
            name="pipeline",
            sub_agents=[OnceAgent(name="step_a"), OnceAgent(name="step_b")],
        )
        seq_events = [event async for event in seq.run(RunContext(input="x"))]
        assert [e.data for e in seq_events if e.type == EventType.FINAL_OUTPUT] == ["step_a", "step_b"]

        loop = LoopAgent(
            name="loop",
            max_iterations=5,
            loop_condition=lambda _ctx, state: state["iteration"] < 1,
            sub_agents=[OnceAgent(name="worker")],
        )
        loop_events = [event async for event in loop.run(RunContext(input="x"))]
        assert any(e.type == "loop_exit" for e in loop_events)

    asyncio.run(_case())


def test_quickstart_runcontext_serialization():
    class SharedState:
        def __init__(self, user_role: str):
            self.user_role = user_role

        def __ak_serialize__(self) -> dict:
            return {"user_role": self.user_role}

        @classmethod
        def __ak_deserialize__(cls, data: dict) -> "SharedState":
            return cls(user_role=data["user_role"])

    ctx = RunContext(input="hello", shared_context=SharedState("admin"), user_id="u-1")
    payload = ctx.to_json()
    restored = RunContext.from_json(payload, shared_context_cls=SharedState)

    assert restored.input == "hello"
    assert restored.user_id == "u-1"
    assert restored.shared_context.user_role == "admin"


def test_quickstart_event_validate_data():
    event = Event(agent="demo", type=EventType.TOOL_RESULT, data={"tool": "add", "result": "42"})
    validated = event.validate_data(ToolResultSchema)
    assert validated.tool == "add"
    assert validated.result == "42"


def test_quickstart_model_cosplay_policy():
    try:
        LockedEchoAgent(name="locked", model="ollama/llama3:8b")
        assert False, "LockedEchoAgent 应禁止实例化覆盖 model"
    except ValueError as exc:
        assert "ModelCosplay 未开启" in str(exc)

    cosplay = CosplayEchoAgent(name="cosplay", model="ollama/llama3:8b")
    assert cosplay.model == "ollama/llama3:8b"

    cosplay.apply_model_cosplay("ollama/qwen2.5:7b")
    assert cosplay.model == "ollama/qwen2.5:7b"
