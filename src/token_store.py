"""Persistence helper for OAuth2 access and refresh tokens."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class OAuth2Token:
    access_token: str
    refresh_token: str
    expires_at: Optional[float] = None
    scope: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at - 30  # allow small buffer


class TokenStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Optional[OAuth2Token]:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        if not access or not refresh:
            return None
        expires_at = payload.get("expires_at")
        return OAuth2Token(
            access_token=access,
            refresh_token=refresh,
            expires_at=float(expires_at) if expires_at is not None else None,
            scope=payload.get("scope"),
        )

    def save(self, token: OAuth2Token) -> None:
        payload = {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
            "scope": token.scope,
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
