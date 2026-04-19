from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from typing import Any

from fastapi import HTTPException

from .config import HubConfig


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def _introspect_token(cfg: HubConfig, token: str) -> dict[str, Any]:
    if not cfg.oauth_introspection_url:
        raise HTTPException(status_code=401, detail="unauthorized")

    body = urllib.parse.urlencode({"token": token}).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if cfg.oauth_client_id and cfg.oauth_client_secret:
        raw = f"{cfg.oauth_client_id}:{cfg.oauth_client_secret}".encode("utf-8")
        headers["Authorization"] = f"Basic {base64.b64encode(raw).decode('utf-8')}"

    req = urllib.request.Request(cfg.oauth_introspection_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network path
        raise HTTPException(status_code=401, detail=f"token_introspection_failed:{exc}") from exc

    if not payload.get("active"):
        raise HTTPException(status_code=401, detail="token_inactive")
    if cfg.oidc_issuer and payload.get("iss") and payload.get("iss") != cfg.oidc_issuer:
        raise HTTPException(status_code=401, detail="invalid_issuer")
    return payload


def authenticate_request(
    cfg: HubConfig,
    *,
    authorization: str | None,
) -> dict[str, Any]:
    """
    Authentication policy:
    1. Authorization: Bearer <token>.
    2. Bearer token can be validated by static api_key or OAuth introspection.
    """
    token = _extract_bearer(authorization)
    if token:
        # Static key mode (keeps current lightweight deployment model)
        if cfg.api_key and token == cfg.api_key:
            return {"auth_type": "api_key", "sub": "api_key_user"}
        # OAuth2/OIDC mode via introspection
        if cfg.oauth_introspection_url:
            claims = _introspect_token(cfg, token)
            return {"auth_type": "oauth", "sub": claims.get("sub"), "claims": claims}
        raise HTTPException(status_code=401, detail="unauthorized")

    # If auth is not configured, keep open mode.
    if not cfg.api_key and not cfg.oauth_introspection_url:
        return {"auth_type": "none", "sub": "anonymous"}

    raise HTTPException(status_code=401, detail="unauthorized")
