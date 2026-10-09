"""本地 rerank sidecar：为 HybridRAGAgent 提供兼容 /api/rerank 的服务。"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, Field

from .providers import OllamaEmbeddingProvider

DEFAULT_RERANK_SERVER_BASE = "http://127.0.0.1:11535"
DEFAULT_RERANK_MODEL = "ollama/qllama/bce-reranker-base_v1:f16"
DEFAULT_FALLBACK_EMBEDDING_MODEL = "ollama/qllama/bge-small-zh-v1.5:f16"

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover - 在未安装 extra 时由 main 给出提示
    FastAPI = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]


class RerankRequest(BaseModel):
    model: str | None = None
    query: str = Field(min_length=1)
    documents: list[str] = Field(default_factory=list)
    top_n: int | None = Field(default=None, ge=1)
    return_documents: bool = False


class RerankResponse(BaseModel):
    model: str
    backend_model: str
    results: list[dict[str, Any]]


@dataclass(slots=True)
class OllamaEmbeddingRerankBackend:
    """
    基于 Ollama /api/embed 的本地打分后端。

    这里对外仍提供 rerank 契约，便于 HybridRAGAgent 直接复用当前 provider。
    """

    model: str
    embedder: Any
    fallback_model: str | None = None
    fallback_embedder: Any | None = None
    last_backend_model: str = field(init=False, default="")

    @classmethod
    def from_ollama(
        cls,
        *,
        model: str,
        ollama_base_url: str,
        timeout: int,
        fallback_model: str | None = DEFAULT_FALLBACK_EMBEDDING_MODEL,
    ) -> "OllamaEmbeddingRerankBackend":
        return cls(
            model=model,
            embedder=OllamaEmbeddingProvider(model=model, api_base=ollama_base_url, timeout=timeout),
            fallback_model=fallback_model,
            fallback_embedder=(
                OllamaEmbeddingProvider(model=fallback_model, api_base=ollama_base_url, timeout=timeout)
                if fallback_model and fallback_model != model
                else None
            ),
        )

    def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int | None = None,
        return_documents: bool = False,
    ) -> list[dict[str, Any]]:
        if not documents:
            return []

        embeddings, backend_model = self._embed_query_and_documents(query, documents)
        self.last_backend_model = backend_model
        query_embedding = embeddings[0]
        document_embeddings = embeddings[1:]

        scored: list[dict[str, Any]] = []
        for idx, document_embedding in enumerate(document_embeddings):
            score = cosine_similarity(query_embedding, document_embedding)
            item: dict[str, Any] = {
                "index": idx,
                "relevance_score": score,
            }
            if return_documents:
                item["document"] = documents[idx]
            scored.append(item)

        scored.sort(key=lambda item: item["relevance_score"], reverse=True)
        if top_n is not None:
            return scored[:top_n]
        return scored

    def _embed_query_and_documents(self, query: str, documents: list[str]) -> tuple[list[list[float]], str]:
        try:
            return self._embed_texts_with_batch_fallback(self.embedder, [query, *documents]), self.model
        except RuntimeError:
            if self.fallback_embedder is None or not self.fallback_model:
                raise
            return (
                self._embed_texts_with_batch_fallback(self.fallback_embedder, [query, *documents]),
                self.fallback_model,
            )

    @staticmethod
    def _embed_texts_with_batch_fallback(embedder: Any, texts: list[str]) -> list[list[float]]:
        try:
            return embedder.embed_texts(texts)
        except RuntimeError:
            embeddings: list[list[float]] = []
            for text in texts:
                embeddings.append(embedder.embed_texts([text])[0])
            return embeddings


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding 维度不一致，无法计算相似度。")

    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def create_app(
    *,
    default_model: str = DEFAULT_RERANK_MODEL,
    ollama_base_url: str = "http://localhost:11434",
    timeout: int = 300,
    fallback_model: str | None = DEFAULT_FALLBACK_EMBEDDING_MODEL,
    backend_factory: Callable[[str], Any] | None = None,
):
    if FastAPI is None or JSONResponse is None:
        raise ImportError(
            "本地 rerank sidecar 需要 fastapi 与 uvicorn。请执行 "
            '`pip install "ni.agentkit[rerank]"`。'
        )

    app = FastAPI(title="AgentKit Local Rerank Server", version="0.1.0")
    backend_cache: dict[str, Any] = {}

    def resolve_backend(model: str):
        if model not in backend_cache:
            factory = backend_factory or (
                lambda current_model: OllamaEmbeddingRerankBackend.from_ollama(
                    model=current_model,
                    ollama_base_url=ollama_base_url,
                    timeout=timeout,
                    fallback_model=fallback_model,
                )
            )
            backend_cache[model] = factory(model)
        return backend_cache[model]

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "default_model": default_model,
            "ollama_base_url": ollama_base_url,
            "fallback_model": fallback_model,
            "mode": "embedding-score-rerank",
        }

    @app.post("/api/rerank")
    @app.post("/v1/rerank")
    def rerank(payload: RerankRequest):
        model = payload.model or default_model
        try:
            backend = resolve_backend(model)
            results = backend.rerank(
                payload.query,
                payload.documents,
                top_n=payload.top_n,
                return_documents=payload.return_documents,
            )
            backend_model = getattr(backend, "last_backend_model", model) or model
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": str(exc),
                        "type": type(exc).__name__,
                    }
                },
            )
        return RerankResponse(model=model, backend_model=backend_model, results=results).model_dump()

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentkit-rerank-server",
        description="启动 AgentKit 本地 rerank sidecar。",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11535)
    parser.add_argument("--model", default=DEFAULT_RERANK_MODEL)
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--fallback-model", default=DEFAULT_FALLBACK_EMBEDDING_MODEL)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)

    if FastAPI is None:
        print(
            '缺少 fastapi / uvicorn，请执行: pip install "ni.agentkit[rerank]"',
            file=sys.stderr,
        )
        return 1

    try:
        import uvicorn
    except ImportError:
        print(
            '缺少 uvicorn，请执行: pip install "ni.agentkit[rerank]"',
            file=sys.stderr,
        )
        return 1

    app = create_app(
        default_model=args.model,
        ollama_base_url=args.ollama_base_url,
        timeout=args.timeout,
        fallback_model=args.fallback_model or None,
    )
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
