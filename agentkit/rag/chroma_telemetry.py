"""Chroma telemetry no-op 实现，避免本地 CLI 输出无关噪音。"""

from __future__ import annotations

from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override


class NoOpProductTelemetryClient(ProductTelemetryClient):
    """忽略所有 telemetry 事件。"""

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        return None
