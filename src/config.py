"""Configuration helpers for the auto-reply bot."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Tuple

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class OpenAISettings:
    api_key: str = field(repr=False)
    model: str
    reply_style_prompt: str


@dataclass(slots=True)
class TwitterSettings:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    search_query: str
    scopes: Tuple[str, ...]


@dataclass(slots=True)
class AppSettings:
    twitter: TwitterSettings
    openai: OpenAISettings
    poll_interval_seconds: int = 300
    max_tweets_per_run: int = 10
    state_path: str = "state.json"
    token_store_path: str = "token_state.json"

    @classmethod
    def from_env(cls) -> "AppSettings":
        def require(name: str) -> str:
            value = os.getenv(name)
            if not value:
                raise RuntimeError(f"Missing required environment variable: {name}")
            return value

        twitter = TwitterSettings(
            client_id=require("TWITTER_CLIENT_ID"),
            client_secret=require("TWITTER_CLIENT_SECRET"),
            access_token=require("TWITTER_ACCESS_TOKEN"),
            refresh_token=require("TWITTER_REFRESH_TOKEN"),
            search_query=require("TWITTER_SEARCH_QUERY"),
            scopes=tuple(os.getenv("TWITTER_SCOPES", "").split()),
        )

        openai_settings = OpenAISettings(
            api_key=require("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            reply_style_prompt=os.getenv(
                "REPLY_STYLE_PROMPT",
                "Respond with a concise, helpful, and positive tone.",
            ),
        )

        poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
        max_tweets = int(os.getenv("MAX_TWEETS_PER_RUN", "10"))
        state_path = os.getenv("STATE_PATH", "state.json")
        token_store_path = os.getenv("TOKEN_STORE_PATH", "token_state.json")

        return cls(
            twitter=twitter,
            openai=openai_settings,
            poll_interval_seconds=poll_interval,
            max_tweets_per_run=max_tweets,
            state_path=state_path,
            token_store_path=token_store_path,
        )
