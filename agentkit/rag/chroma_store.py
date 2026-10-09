"""agentkit/rag/chroma_store.py — ChromaDB 本地持久化向量存储。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .chunkers import RecursiveTokenChunker
from .loaders import DocumentLoader, default_loaders
from .providers import Embedder
from .types import DocumentChunk, SearchHit


class ChromaVectorStore:
    """基于 ChromaDB 的本地持久化向量存储。"""

    def __init__(
        self,
        *,
        vector_store_dir: str,
        collection_name: str,
        embedding_model: str,
        loaders: list[DocumentLoader] | None = None,
    ) -> None:
        self.vector_store_dir = str(Path(vector_store_dir).expanduser())
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self._loaders = loaders or default_loaders()
        self._loader_by_suffix = {
            suffix: loader
            for loader in self._loaders
            for suffix in loader.suffixes
        }
        self._manifest_path = Path(self.vector_store_dir) / "manifest.json"
        self._chunks_path = Path(self.vector_store_dir) / "chunks.json"
        self._collection = None

    def reload_from_directory(
        self,
        *,
        knowledge_dir: str,
        chunker: RecursiveTokenChunker,
        embedder: Embedder,
        supported_suffixes: tuple[str, ...],
    ) -> list[DocumentChunk]:
        base = Path(knowledge_dir)
        base.mkdir(parents=True, exist_ok=True)
        current_sources = self._scan_sources(base, supported_suffixes)
        manifest = self._read_json(self._manifest_path)
        current_signature = self._build_signature(current_sources, chunker)

        if manifest == current_signature and self._chunks_path.exists():
            return self._load_cached_chunks()

        chunks = self._build_chunks(base, current_sources, chunker)
        self._rebuild_collection(chunks, embedder)
        self._write_json(self._manifest_path, current_signature)
        self._write_json(self._chunks_path, [asdict(chunk) for chunk in chunks])
        return chunks

    def search(self, query: str, *, top_k: int, embedder: Embedder) -> list[SearchHit]:
        if top_k <= 0:
            return []
        collection = self._get_collection()
        available = int(collection.count())
        if available <= 0:
            return []
        query_vector = embedder.embed_texts([query])[0]
        result = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, available),
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        hits: list[SearchHit] = []
        for idx, document in enumerate(documents):
            metadata = metadatas[idx] if idx < len(metadatas) else {}
            distance = float(distances[idx]) if idx < len(distances) else 1.0
            hits.append(
                SearchHit(
                    content=document,
                    source=str(metadata.get("source", "")),
                    score=max(0.0, 1.0 - distance),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    retriever="vector",
                )
            )
        return hits

    def _scan_sources(self, base: Path, supported_suffixes: tuple[str, ...]) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        for path in sorted(
            item for item in base.rglob("*") if item.is_file() and item.suffix.lower() in supported_suffixes
        ):
            sources.append(
                {
                    "source": str(path.relative_to(base)),
                    "absolute_path": str(path.resolve()),
                    "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "suffix": path.suffix.lower(),
                }
            )
        return sources

    def _build_signature(self, sources: list[dict[str, str]], chunker: RecursiveTokenChunker) -> dict[str, Any]:
        return {
            "embedding_model": self.embedding_model,
            "chunk_size_tokens": chunker.chunk_size_tokens,
            "chunk_overlap_tokens": chunker.chunk_overlap_tokens,
            "sources": sources,
        }

    def _build_chunks(
        self,
        base: Path,
        sources: list[dict[str, str]],
        chunker: RecursiveTokenChunker,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for source_info in sources:
            source = source_info["source"]
            path = Path(source_info["absolute_path"])
            loader = self._resolve_loader(path)
            content = loader.load(path)
            if not content:
                continue
            parts = chunker.split_text(content)
            for index, part in enumerate(parts):
                chunk_id = self._chunk_id(source, index, part)
                chunks.append(
                    DocumentChunk(
                        id=chunk_id,
                        content=part,
                        source=source,
                        chunk_index=index,
                        metadata={"loader": loader.name, "suffix": path.suffix.lower()},
                    )
                )
        return chunks

    def _rebuild_collection(self, chunks: list[DocumentChunk], embedder: Embedder) -> None:
        client = self._get_client()
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine", "embedding_model": self.embedding_model},
        )
        if not chunks:
            return

        batch_size = 32
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            documents = [chunk.content for chunk in batch]
            embeddings = embedder.embed_texts(documents)
            self._collection.add(
                ids=[chunk.id for chunk in batch],
                documents=documents,
                embeddings=embeddings,
                metadatas=[
                    {
                        "source": chunk.source,
                        "chunk_index": chunk.chunk_index,
                        "suffix": str(chunk.metadata.get("suffix", "")),
                    }
                    for chunk in batch
                ],
            )

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        client = self._get_client()
        self._collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine", "embedding_model": self.embedding_model},
        )
        return self._collection

    def _get_client(self):
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            raise ImportError(
                "HybridRAGAgent 需要安装 chromadb。请执行 `pip install \"ni.agentkit[rag]\"` 或单独安装 chromadb。"
            ) from exc
        Path(self.vector_store_dir).mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(
            path=self.vector_store_dir,
            settings=Settings(
                anonymized_telemetry=False,
                chroma_product_telemetry_impl="agentkit.rag.chroma_telemetry.NoOpProductTelemetryClient",
                chroma_telemetry_impl="agentkit.rag.chroma_telemetry.NoOpProductTelemetryClient",
            ),
        )

    def _load_cached_chunks(self) -> list[DocumentChunk]:
        data = self._read_json(self._chunks_path) or []
        return [
            DocumentChunk(
                id=item["id"],
                content=item["content"],
                source=item["source"],
                chunk_index=int(item["chunk_index"]),
                metadata=item.get("metadata") or {},
            )
            for item in data
        ]

    def _resolve_loader(self, path: Path) -> DocumentLoader:
        loader = self._loader_by_suffix.get(path.suffix.lower())
        if loader is None:
            raise ValueError(f"不支持的文档类型: {path.suffix.lower()}")
        return loader

    @staticmethod
    def _chunk_id(source: str, chunk_index: int, content: str) -> str:
        seed = f"{source}:{chunk_index}:{content[:120]}".encode("utf-8")
        return hashlib.md5(seed).hexdigest()[:16]

    @staticmethod
    def _read_json(path: Path) -> Any:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
