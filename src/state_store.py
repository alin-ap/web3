"""JSON-backed persistence for processed tweet IDs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class BotState:
    last_seen_id: Optional[int]
    processed_ids: list[int]


class StateStore:
    def __init__(self, path: str, max_history: int = 500) -> None:
        self._path = Path(path)
        self._max_history = max_history
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> BotState:
        if not self._path.exists():
            return BotState(last_seen_id=None, processed_ids=[])
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return BotState(last_seen_id=None, processed_ids=[])
        last_seen = payload.get("last_seen_id")
        processed = payload.get("processed_ids", [])
        return BotState(
            last_seen_id=int(last_seen) if last_seen is not None else None,
            processed_ids=[int(x) for x in processed if isinstance(x, (int, str))],
        )

    def save(self, state: BotState) -> None:
        payload = {
            "last_seen_id": state.last_seen_id,
            "processed_ids": state.processed_ids[-self._max_history :],
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def is_processed(self, tweet_id: int) -> bool:
        state = self.load()
        return tweet_id in state.processed_ids

    def mark_processed(self, tweet_id: int) -> BotState:
        state = self.load()
        if tweet_id not in state.processed_ids:
            state.processed_ids.append(tweet_id)
        if state.last_seen_id is None or tweet_id > state.last_seen_id:
            state.last_seen_id = tweet_id
        self.save(state)
        return state

    def update_last_seen(self, tweet_id: int) -> None:
        state = self.load()
        if state.last_seen_id is None or tweet_id > state.last_seen_id:
            state.last_seen_id = tweet_id
        self.save(state)
