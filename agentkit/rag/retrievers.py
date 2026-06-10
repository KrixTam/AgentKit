"""agentkit/rag/retrievers.py — TF-IDF / BM25 / Vector 检索器"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

from .types import DocumentChunk, SearchHit


def tokenize(text: str) -> list[str]:
    """中英文轻量切词：英文单词 + 中文字与二元组。"""
    tokens: list[str] = []
    tokens.extend(re.findall(r"[a-zA-Z]+", text.lower()))
    zh_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i, c in enumerate(zh_chars):
        tokens.append(c)
        if i + 1 < len(zh_chars):
            tokens.append(c + zh_chars[i + 1])
    return tokens


class Retriever(Protocol):
    name: str

    def build(self, chunks: list[DocumentChunk]) -> None:
        ...

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        ...


class TfidfRetriever:
    name = "tfidf"

    def __init__(self) -> None:
        self._chunks: list[DocumentChunk] = []
        self._idf: dict[str, float] = {}
        self._vectors: list[dict[str, float]] = []

    def build(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = chunks
        self._idf = {}
        self._vectors = []
        if not chunks:
            return

        n = len(chunks)
        df = Counter()
        chunk_counts: list[Counter[str]] = []
        for chunk in chunks:
            counts = Counter(tokenize(chunk.content))
            chunk_counts.append(counts)
            for token in set(counts.keys()):
                df[token] += 1
        self._idf = {token: math.log((n + 1) / (freq + 1)) + 1 for token, freq in df.items()}

        for counts in chunk_counts:
            total = sum(counts.values()) or 1
            vec: dict[str, float] = {}
            for token, cnt in counts.items():
                tf = cnt / total
                vec[token] = tf * self._idf.get(token, 1.0)
            self._vectors.append(vec)

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        if not self._chunks:
            return []

        q_counts = Counter(tokenize(query))
        total = sum(q_counts.values()) or 1
        q_vec = {t: (c / total) * self._idf.get(t, 1.0) for t, c in q_counts.items()}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scores: list[tuple[float, int]] = []
        for idx, c_vec in enumerate(self._vectors):
            dot = sum(q_vec.get(t, 0.0) * c_vec.get(t, 0.0) for t in q_vec.keys())
            c_norm = math.sqrt(sum(v * v for v in c_vec.values())) or 1.0
            sim = dot / (q_norm * c_norm)
            if sim > 0:
                scores.append((sim, idx))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchHit(
                content=self._chunks[idx].content,
                source=self._chunks[idx].source,
                score=score,
                chunk_index=self._chunks[idx].chunk_index,
                retriever=self.name,
            )
            for score, idx in scores[:top_k]
        ]


class BM25Retriever:
    name = "bm25"

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._chunks: list[DocumentChunk] = []
        self._idf: dict[str, float] = {}
        self._doc_tf: list[Counter[str]] = []
        self._doc_len: list[int] = []
        self._avg_len: float = 0.0

    def build(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = chunks
        self._idf = {}
        self._doc_tf = []
        self._doc_len = []
        self._avg_len = 0.0
        if not chunks:
            return

        df = Counter()
        for chunk in chunks:
            tf = Counter(tokenize(chunk.content))
            self._doc_tf.append(tf)
            self._doc_len.append(sum(tf.values()))
            for t in set(tf.keys()):
                df[t] += 1

        n = len(chunks)
        self._avg_len = sum(self._doc_len) / max(n, 1)
        self._idf = {
            t: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
            for t, freq in df.items()
        }

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        if not self._chunks:
            return []
        q_terms = tokenize(query)

        scored: list[tuple[float, int]] = []
        for idx, tf in enumerate(self._doc_tf):
            score = 0.0
            dl = self._doc_len[idx] or 1
            for term in q_terms:
                f = tf.get(term, 0)
                if f <= 0:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = f + self.k1 * (1 - self.b + self.b * dl / max(self._avg_len, 1))
                score += idf * (f * (self.k1 + 1)) / max(denom, 1e-8)
            if score > 0:
                scored.append((score, idx))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchHit(
                content=self._chunks[idx].content,
                source=self._chunks[idx].source,
                score=score,
                chunk_index=self._chunks[idx].chunk_index,
                retriever=self.name,
            )
            for score, idx in scored[:top_k]
        ]


class Embedder(Protocol):
    """向量化接口，便于后续接入任意 embedding provider。"""

    def embed(self, text: str) -> list[float]:
        ...


class HashingEmbedder:
    """无外部依赖的本地向量化实现（V1 默认）。"""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in tokenize(text):
            h = hash(token) % self.dim
            vec[h] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class VectorRetriever:
    name = "vector"

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._embedder = embedder or HashingEmbedder()
        self._chunks: list[DocumentChunk] = []
        self._vectors: list[list[float]] = []

    def build(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = chunks
        self._vectors = [self._embedder.embed(c.content) for c in chunks]

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        if not self._chunks:
            return []
        q_vec = self._embedder.embed(query)
        scored: list[tuple[float, int]] = []
        for idx, c_vec in enumerate(self._vectors):
            score = sum(q * c for q, c in zip(q_vec, c_vec))
            if score > 0:
                scored.append((score, idx))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchHit(
                content=self._chunks[idx].content,
                source=self._chunks[idx].source,
                score=score,
                chunk_index=self._chunks[idx].chunk_index,
                retriever=self.name,
            )
            for score, idx in scored[:top_k]
        ]
