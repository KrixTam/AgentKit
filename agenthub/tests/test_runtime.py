from __future__ import annotations

import time

import pytest

from agenthub.runtime import QuotaManager


def test_quota_manager_enforces_concurrency_limit():
    quota = QuotaManager(max_concurrency_per_user=1, rate_limit_per_minute=10)

    quota.acquire("tenant:u1")
    with pytest.raises(ValueError, match="quota_exceeded:concurrency"):
        quota.acquire("tenant:u1")
    quota.release("tenant:u1")
    quota.acquire("tenant:u1")


def test_quota_manager_enforces_rate_limit_and_window(monkeypatch):
    current = {"now": 1000.0}

    def _now() -> float:
        return current["now"]

    monkeypatch.setattr(time, "time", _now)
    quota = QuotaManager(max_concurrency_per_user=2, rate_limit_per_minute=2)

    quota.acquire("tenant:u1")
    quota.release("tenant:u1")
    quota.acquire("tenant:u1")
    quota.release("tenant:u1")

    with pytest.raises(ValueError, match="quota_exceeded:rate"):
        quota.acquire("tenant:u1")

    current["now"] += 61.0
    quota.acquire("tenant:u1")
