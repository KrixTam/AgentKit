"""
agentkit/llm/registry.py — 模型注册中心

根据模型标识前缀自动选择适配器，零配置即可使用：
  "gpt-4o"               → OpenAIAdapter
  "claude-sonnet-4-20250514"     → AnthropicAdapter
  "gemini-2.5-pro"       → GoogleAdapter
  "deepseek/deepseek-chat" → OpenAICompatibleAdapter
"""
from __future__ import annotations

import os
from typing import Any

from .base import BaseLLM
from .types import LLMConfig


class LLMRegistry:
    """模型注册中心"""

    _default_model: str = "gpt-4o"
    _default_config: LLMConfig | None = None
    _custom_adapters: dict[str, type[BaseLLM]] = {}

    # 前缀 → 适配器类（延迟导入避免未安装的 SDK 报错）
    _PREFIX_MAP: dict[str, str] = {
        "gpt-":      "openai",
        "o1":        "openai",
        "o3":        "openai",
        "o4":        "openai",
        "claude-":   "anthropic",
        "gemini-":   "google",
        "ollama/":   "ollama",
        "deepseek/": "compatible",
        "qwen/":     "compatible",
        "zhipu/":    "compatible",
        "moonshot/": "compatible",
        "baichuan/": "compatible",
        "azure/":    "compatible",
    }

    @classmethod
    def set_default(cls, model: str, **kwargs: Any) -> None:
        cls._default_model = model
        cls._default_config = LLMConfig(model=model, **kwargs)

    @classmethod
    def register(cls, prefix: str, adapter_class: type[BaseLLM]) -> None:
        cls._custom_adapters[prefix] = adapter_class

    @classmethod
    def create(cls, model_or_config: str | LLMConfig | BaseLLM) -> BaseLLM:
        if isinstance(model_or_config, BaseLLM):
            return model_or_config

        # 保留原始标识用于路由
        original_model_str: str | None = None

        config: LLMConfig
        if isinstance(model_or_config, str):
            original_model_str = model_or_config
            config = cls._build_config_from_string(model_or_config)
        elif isinstance(model_or_config, LLMConfig):
            original_model_str = model_or_config.model
            config = model_or_config
        else:
            raise ValueError(f"不支持的参数类型: {type(model_or_config)}")

        # 用原始字符串做前缀路由（因为 config.model 可能已被去掉 provider/ 前缀）
        adapter_class = cls._resolve_adapter(original_model_str or config.model)
        return adapter_class(config)

    @classmethod
    def create_default(cls) -> BaseLLM:
        if cls._default_config:
            return cls.create(cls._default_config)
        return cls.create(cls._default_model)

    # ------------------------------------------------------------------

    @classmethod
    def _resolve_adapter(cls, model: str) -> type[BaseLLM]:
        # 1. 自定义注册
        for prefix, adapter_cls in cls._custom_adapters.items():
            if model.startswith(prefix):
                return adapter_cls

        # 2. 内置映射
        for prefix, adapter_key in cls._PREFIX_MAP.items():
            if model.startswith(prefix):
                return cls._import_adapter(adapter_key)

        # 3. 默认 OpenAI 兼容
        return cls._import_adapter("compatible")

    @classmethod
    def _import_adapter(cls, key: str) -> type[BaseLLM]:
        if key == "openai":
            from .adapters.openai_adapter import OpenAIAdapter
            return OpenAIAdapter
        if key == "anthropic":
            from .adapters.anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter
        if key == "google":
            from .adapters.google_adapter import GoogleAdapter
            return GoogleAdapter
        if key == "ollama":
            from .adapters.ollama_adapter import OllamaAdapter
            return OllamaAdapter
        from .adapters.openai_compatible import OpenAICompatibleAdapter
        return OpenAICompatibleAdapter

    @classmethod
    def _build_config_from_string(cls, model_str: str) -> LLMConfig:
        from .adapters.openai_compatible import PROVIDER_ENDPOINTS, PROVIDER_ENV_KEYS

        config_kwargs: dict[str, Any] = {"model": model_str}

        if "/" in model_str:
            provider, actual_model = model_str.split("/", 1)

            # Ollama 特殊处理
            if provider == "ollama":
                config_kwargs["model"] = actual_model
                config_kwargs["api_base"] = "http://localhost:11434"
                return LLMConfig(**config_kwargs)

            if provider in PROVIDER_ENDPOINTS and PROVIDER_ENDPOINTS[provider]:
                config_kwargs["api_base"] = PROVIDER_ENDPOINTS[provider]
            if provider in PROVIDER_ENV_KEYS:
                env_key = PROVIDER_ENV_KEYS[provider]
                api_key = os.environ.get(env_key)
                if api_key:
                    config_kwargs["api_key"] = api_key
            config_kwargs["model"] = actual_model

        return LLMConfig(**config_kwargs)
