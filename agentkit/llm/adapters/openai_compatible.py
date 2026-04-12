"""
agentkit/llm/adapters/openai_compatible.py — OpenAI 兼容厂商适配器

覆盖：通义千问、智谱 GLM、DeepSeek、Moonshot、百川、Azure OpenAI
原理：这些厂商的 API 格式完全兼容 OpenAI，只需替换 api_base + api_key。
"""
from __future__ import annotations

from .openai_adapter import OpenAIAdapter


class OpenAICompatibleAdapter(OpenAIAdapter):
    """OpenAI 兼容厂商的通用适配器——直接复用 OpenAIAdapter 全部逻辑"""
    pass


# 各厂商的默认 API 端点
PROVIDER_ENDPOINTS: dict[str, str | None] = {
    "deepseek":  "https://api.deepseek.com/v1",
    "qwen":      "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu":     "https://open.bigmodel.cn/api/paas/v4",
    "moonshot":  "https://api.moonshot.cn/v1",
    "baichuan":  "https://api.baichuan-ai.com/v1",
    "azure":     None,
}

# 各厂商的 API Key 环境变量名
PROVIDER_ENV_KEYS: dict[str, str] = {
    "deepseek":  "DEEPSEEK_API_KEY",
    "qwen":      "DASHSCOPE_API_KEY",
    "zhipu":     "ZHIPU_API_KEY",
    "moonshot":  "MOONSHOT_API_KEY",
    "baichuan":  "BAICHUAN_API_KEY",
    "azure":     "AZURE_OPENAI_API_KEY",
}
