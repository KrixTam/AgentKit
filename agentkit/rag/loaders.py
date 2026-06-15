"""agentkit/rag/loaders.py — 文档加载器。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DocumentLoader(Protocol):
    name: str
    suffixes: tuple[str, ...]

    def load(self, path: Path) -> str:
        ...


@dataclass(frozen=True)
class TextLoader:
    name: str = "text"
    suffixes: tuple[str, ...] = (".txt",)

    def load(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore").strip()


@dataclass(frozen=True)
class MarkdownLoader:
    name: str = "markdown"
    suffixes: tuple[str, ...] = (".md", ".markdown")

    def load(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore").strip()


@dataclass(frozen=True)
class PdfLoader:
    name: str = "pdf"
    suffixes: tuple[str, ...] = (".pdf",)

    def load(self, path: Path) -> str:
        text = self._extract_text(path).strip()
        if not text:
            return ""
        return text

    def _extract_text(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "检测到 PDF 文件，但当前环境未安装 pypdf。"
                '请执行 `pip install "ni.agentkit[pdf]"` 或 `pip install pypdf`。'
            ) from exc

        reader = PdfReader(str(path))
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)


def default_loaders() -> list[DocumentLoader]:
    return [TextLoader(), MarkdownLoader(), PdfLoader()]
