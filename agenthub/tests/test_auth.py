from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agenthub.auth import authenticate_request
from agenthub.config import HubConfig


class _MockHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_authenticate_with_static_bearer():
    cfg = HubConfig(api_key="secret")
    result = authenticate_request(cfg, authorization="Bearer secret")
    assert result["auth_type"] == "api_key"


def test_authenticate_with_oauth_introspection(monkeypatch):
    cfg = HubConfig(
        oauth_introspection_url="https://idp.example.com/oauth2/introspect",
        oauth_client_id="cid",
        oauth_client_secret="csecret",
        oidc_issuer="https://idp.example.com",
    )

    def _mock_urlopen(_req, timeout=5):
        assert timeout == 5
        return _MockHTTPResponse({"active": True, "sub": "u-1", "iss": "https://idp.example.com"})

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _mock_urlopen)
    result = authenticate_request(cfg, authorization="Bearer oauth_token")
    assert result["auth_type"] == "oauth"
    assert result["sub"] == "u-1"


def test_authenticate_rejects_inactive_token(monkeypatch):
    cfg = HubConfig(oauth_introspection_url="https://idp.example.com/introspect")

    def _mock_urlopen(_req, timeout=5):
        assert timeout == 5
        return _MockHTTPResponse({"active": False})

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _mock_urlopen)
    with pytest.raises(HTTPException) as exc:
        authenticate_request(cfg, authorization="Bearer bad_token")
    assert exc.value.status_code == 401
    assert "token_inactive" in str(exc.value.detail)
