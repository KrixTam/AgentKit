"""agentkit/rag/providers.py — Embedding 与 Reranker Provider。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request


DEFAULT_OLLAMA_BASE = "http://localhost:11434"


class Embedder(Protocol):
    model: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class Reranker(Protocol):
    model: str

    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        ...


def strip_ollama_prefix(model: str) -> str:
    return model.split("/", 1)[1] if model.startswith("ollama/") else model


def post_json(url: str, payload: dict, *, timeout: int) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"请求失败 ({exc.code}) {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"无法连接服务 {url}: {exc.reason}") from exc
    return json.loads(raw or "{}")


@dataclass
class OllamaEmbeddingProvider:
    """通过 Ollama `/api/embed` 生成 embedding。"""

    model: str
    api_base: str | None = None
    timeout: int = 300

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": strip_ollama_prefix(self.model),
            "input": texts if len(texts) > 1 else texts[0],
        }
        url = f"{(self.api_base or DEFAULT_OLLAMA_BASE).rstrip('/')}/api/embed"
        data = post_json(url, payload, timeout=self.timeout)
        embeddings = data.get("embeddings")
        if embeddings is None and "embedding" in data:
            embeddings = [data["embedding"]]
        if not isinstance(embeddings, list) or not embeddings:
            raise RuntimeError("Ollama embedding 响应缺少 embeddings 字段。")
        if embeddings and isinstance(embeddings[0], (int, float)):
            return [embeddings]  # 兼容单条 embedding 返回
        return embeddings


@dataclass
class OllamaReranker:
    """
    通过兼容 `/api/rerank` 或 `/v1/rerank` 的本地服务进行重排。

    默认建议配合 `agentkit-rerank-server` 使用，也兼容其他实现相同协议的本地服务。
    """

    model: str
    api_base: str | None = None
    timeout: int = 300
    api_paths: tuple[str, ...] = ("/api/rerank", "/v1/rerank")

    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        if not documents:
            return []
        base = (self.api_base or DEFAULT_OLLAMA_BASE).rstrip("/")
        payload = {
            "model": strip_ollama_prefix(self.model),
            "query": query,
            "documents": documents,
        }

        last_error: Exception | None = None
        for api_path in self.api_paths:
            try:
                data = post_json(f"{base}{api_path}", payload, timeout=self.timeout)
            except RuntimeError as exc:
                last_error = exc
                continue

            results = data.get("results")
            if not isinstance(results, list):
                continue
            scored: list[tuple[int, float]] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                index = item.get("index")
                score = item.get("relevance_score", item.get("score"))
                if isinstance(index, int) and isinstance(score, (int, float)):
                    scored.append((index, float(score)))
            if scored:
                scored.sort(key=lambda item: item[1], reverse=True)
                return scored

        message = (
            "未命中可用的 rerank 接口。请确认本地已启动 `agentkit-rerank-server` "
            "或其他兼容 `/api/rerank` / `/v1/rerank` 的服务，并检查 "
            "reranker_base_url / reranker_model 配置。"
        )
        if last_error is not None:
            raise RuntimeError(f"{message} 原始错误: {last_error}") from last_error
        raise RuntimeError(message)
