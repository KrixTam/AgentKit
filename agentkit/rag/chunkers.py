"""agentkit/rag/chunkers.py — HybridRAGAgent 文本切块器。"""

from __future__ import annotations

import re
from dataclasses import dataclass


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]|[^\w\s]", re.UNICODE)


@dataclass
class RecursiveTokenChunker:
    """按段落、行、句子递归切分，并以 token 预算合并。"""

    chunk_size_tokens: int = 350
    chunk_overlap_tokens: int = 50

    def count_tokens(self, text: str) -> int:
        return len(self._token_spans(text))

    def split_text(self, text: str) -> list[str]:
        normalized = text.replace("\r\n", "\n").strip()
        if not normalized:
            return []
        units = self._split_recursive(normalized, separators=["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; "])
        return self._merge_units(units)

    def _split_recursive(self, text: str, *, separators: list[str]) -> list[str]:
        text = text.strip()
        if not text:
            return []
        if self.count_tokens(text) <= self.chunk_size_tokens:
            return [text]
        if not separators:
            return self._hard_split(text)

        separator = separators[0]
        parts = [part.strip() for part in text.split(separator) if part.strip()]
        if len(parts) <= 1:
            return self._split_recursive(text, separators=separators[1:])

        chunks: list[str] = []
        for part in parts:
            chunks.extend(self._split_recursive(part, separators=separators[1:]))
        return chunks

    def _merge_units(self, units: list[str]) -> list[str]:
        merged: list[str] = []
        current = ""

        for unit in units:
            unit = unit.strip()
            if not unit:
                continue

            candidate = unit if not current else f"{current}\n{unit}"
            if self.count_tokens(candidate) <= self.chunk_size_tokens:
                current = candidate
                continue

            if current:
                merged.append(current.strip())
                overlap = self._last_tokens(current, self.chunk_overlap_tokens)
                current = f"{overlap}\n{unit}".strip() if overlap else unit
                if self.count_tokens(current) <= self.chunk_size_tokens:
                    continue

            oversized = self._hard_split(unit)
            if not oversized:
                current = ""
                continue
            merged.extend(oversized[:-1])
            current = oversized[-1]

        if current:
            merged.append(current.strip())
        return [chunk for chunk in merged if chunk]

    def _hard_split(self, text: str) -> list[str]:
        spans = self._token_spans(text)
        if not spans:
            return []

        chunks: list[str] = []
        step = max(1, self.chunk_size_tokens - self.chunk_overlap_tokens)
        for start_idx in range(0, len(spans), step):
            end_idx = min(start_idx + self.chunk_size_tokens, len(spans))
            start_char = spans[start_idx][0]
            end_char = spans[end_idx - 1][1]
            chunk = text[start_char:end_char].strip()
            if chunk:
                chunks.append(chunk)
            if end_idx >= len(spans):
                break
        return chunks

    def _last_tokens(self, text: str, count: int) -> str:
        if count <= 0:
            return ""
        spans = self._token_spans(text)
        if not spans:
            return ""
        if len(spans) <= count:
            return text.strip()
        start_char = spans[-count][0]
        return text[start_char:].strip()

    @staticmethod
    def _token_spans(text: str) -> list[tuple[int, int]]:
        return [match.span() for match in TOKEN_RE.finditer(text)]
