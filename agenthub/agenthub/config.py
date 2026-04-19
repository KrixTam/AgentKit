from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class HubConfig:
    host: str = "0.0.0.0"
    port: int = 8008
    store_type: str = "sqlite"  # memory | sqlite
    sqlite_path: str = ".agenthub/agenthub.db"
    api_key: str | None = None
    max_concurrency_per_user: int = 8
    rate_limit_per_minute: int = 120

    @classmethod
    def from_env(cls) -> "HubConfig":
        return cls(
            host=os.getenv("AGENTHUB_HOST", "0.0.0.0"),
            port=int(os.getenv("AGENTHUB_PORT", "8008")),
            store_type=os.getenv("AGENTHUB_STORE", "sqlite"),
            sqlite_path=os.getenv("AGENTHUB_SQLITE_PATH", ".agenthub/agenthub.db"),
            api_key=os.getenv("AGENTHUB_API_KEY"),
            max_concurrency_per_user=int(os.getenv("AGENTHUB_MAX_CONCURRENCY_PER_USER", "8")),
            rate_limit_per_minute=int(os.getenv("AGENTHUB_RATE_LIMIT_PER_MINUTE", "120")),
        )
