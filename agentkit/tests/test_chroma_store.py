from __future__ import annotations

from agentkit.rag.chroma_store import ChromaVectorStore


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class FakeCollection:
    def __init__(self, count: int) -> None:
        self._count = count
        self.last_n_results: int | None = None

    def count(self) -> int:
        return self._count

    def query(self, *, query_embeddings, n_results, include):
        self.last_n_results = n_results
        return {
            "documents": [["交易法则说明"][:n_results]],
            "metadatas": [[{"source": "guide.md", "chunk_index": 0}][:n_results]],
            "distances": [[0.1][:n_results]],
        }


def test_chroma_search_caps_n_results_to_collection_size(tmp_path):
    store = ChromaVectorStore(
        vector_store_dir=str(tmp_path / "chroma"),
        collection_name="demo",
        embedding_model="ollama/qllama/bge-small-zh-v1.5:f16",
    )
    collection = FakeCollection(count=1)
    store._collection = collection

    hits = store.search("交易法则", top_k=20, embedder=FakeEmbedder())

    assert collection.last_n_results == 1
    assert len(hits) == 1
    assert hits[0].source == "guide.md"


def test_chroma_search_returns_empty_when_collection_is_empty(tmp_path):
    store = ChromaVectorStore(
        vector_store_dir=str(tmp_path / "chroma"),
        collection_name="demo",
        embedding_model="ollama/qllama/bge-small-zh-v1.5:f16",
    )
    collection = FakeCollection(count=0)
    store._collection = collection

    hits = store.search("交易法则", top_k=20, embedder=FakeEmbedder())

    assert hits == []
    assert collection.last_n_results is None
