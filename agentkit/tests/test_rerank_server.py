from __future__ import annotations

from agentkit.rag.rerank_server import OllamaEmbeddingRerankBackend, cosine_similarity, create_app


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        mapping = {
            "交易法则": [1.0, 0.0],
            "顺势而为和仓位控制": [0.95, 0.05],
            "今天适合吃什么": [0.0, 1.0],
        }
        return [mapping[text] for text in texts]


class FakeBackend:
    last_backend_model = "demo-backend"

    def rerank(self, query: str, documents: list[str], *, top_n=None, return_documents=False):
        results = [
            {"index": 1, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.4},
        ]
        if return_documents:
            for item in results:
                item["document"] = documents[item["index"]]
        if top_n is not None:
            return results[:top_n]
        return results


class BatchFragileEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if len(texts) > 1:
            raise RuntimeError("batch not supported")
        mapping = {
            "交易法则": [1.0, 0.0],
            "顺势而为和仓位控制": [0.95, 0.05],
            "今天适合吃什么": [0.0, 1.0],
        }
        return [mapping[texts[0]]]


class AlwaysFailEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embed failed")


class FallbackEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        mapping = {
            "交易法则": [1.0, 0.0],
            "顺势而为和仓位控制": [0.95, 0.05],
            "今天适合吃什么": [0.0, 1.0],
        }
        return [mapping[text] for text in texts]


def test_cosine_similarity_orders_related_documents_first():
    backend = OllamaEmbeddingRerankBackend(model="ollama/qllama/bce-reranker-base_v1:f16", embedder=FakeEmbedder())
    results = backend.rerank(
        "交易法则",
        ["今天适合吃什么", "顺势而为和仓位控制"],
        top_n=1,
        return_documents=True,
    )

    assert len(results) == 1
    assert results[0]["index"] == 1
    assert results[0]["document"] == "顺势而为和仓位控制"
    assert results[0]["relevance_score"] > 0.9


def test_cosine_similarity_handles_zero_norm():
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_backend_falls_back_to_single_item_embed_when_batch_is_unavailable():
    backend = OllamaEmbeddingRerankBackend(
        model="ollama/qllama/bce-reranker-base_v1:f16",
        embedder=BatchFragileEmbedder(),
    )

    results = backend.rerank("交易法则", ["今天适合吃什么", "顺势而为和仓位控制"], top_n=1)

    assert results[0]["index"] == 1


def test_backend_falls_back_to_secondary_model_when_primary_embed_fails():
    backend = OllamaEmbeddingRerankBackend(
        model="ollama/qllama/bce-reranker-base_v1:f16",
        embedder=AlwaysFailEmbedder(),
        fallback_model="ollama/qllama/bge-small-zh-v1.5:f16",
        fallback_embedder=FallbackEmbedder(),
    )

    results = backend.rerank("交易法则", ["今天适合吃什么", "顺势而为和仓位控制"], top_n=1)

    assert results[0]["index"] == 1
    assert backend.last_backend_model == "ollama/qllama/bge-small-zh-v1.5:f16"


def test_rerank_server_http_contract_if_fastapi_is_available():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        return

    app = create_app(default_model="demo-reranker", backend_factory=lambda _model: FakeBackend())
    client = TestClient(app)

    resp = client.post(
        "/v1/rerank",
        json={
            "query": "交易法则",
            "documents": ["文档A", "文档B"],
            "top_n": 1,
            "return_documents": True,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "demo-reranker"
    assert data["backend_model"] == "demo-backend"
    assert data["results"][0]["index"] == 1
    assert data["results"][0]["document"] == "文档B"
