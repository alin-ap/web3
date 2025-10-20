"""Unified persistence helpers for bot state and OAuth tokens."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class BotState:
    last_seen_id: Optional[int] = None
    processed_ids: list[int] = field(default_factory=list)


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
        return time.time() >= self.expires_at - 30  # small buffer to avoid edge cases


class Storage:
    def __init__(self, state_path: str, token_path: str, *, max_history: int = 500) -> None:
        self._state_path = Path(state_path)
        self._token_path = Path(token_path)
        self._max_history = max_history
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.parent.mkdir(parents=True, exist_ok=True)

    # Bot state helpers -------------------------------------------------
    def load_state(self) -> BotState:
        if not self._state_path.exists():
            return BotState()
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return BotState()
        last_seen = payload.get("last_seen_id")
        processed = payload.get("processed_ids", [])
        cleaned: list[int] = []
        for item in processed:
            if isinstance(item, int):
                cleaned.append(item)
            elif isinstance(item, str) and item.isdigit():
                cleaned.append(int(item))
        return BotState(
            last_seen_id=int(last_seen) if last_seen is not None else None,
            processed_ids=cleaned,
        )

    def save_state(self, state: BotState) -> None:
        payload = {
            "last_seen_id": state.last_seen_id,
            "processed_ids": state.processed_ids[-self._max_history :],
        }
        self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Token helpers -----------------------------------------------------
    def load_token(self) -> Optional[OAuth2Token]:
        if not self._token_path.exists():
            return None
        try:
            payload = json.loads(self._token_path.read_text(encoding="utf-8"))
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

    def save_token(self, token: OAuth2Token) -> None:
        payload = {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
            "scope": token.scope,
        }
        self._token_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
