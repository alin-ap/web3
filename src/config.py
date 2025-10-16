"""Configuration helpers for the auto-reply bot."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

from dotenv import load_dotenv


load_dotenv()


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_CLASSIFIER_MODEL = "gpt-5-nano"
DEFAULT_REPLY_PROMPT = (
    "You speak for PunkStrategyStrategy ($PSS), an autonomous on-chain meta-strategy engine on Ethereum. "
    "Highlight that trading fees are recycled into PNKSTR/ETH liquidity and used to buy back & burn $PSS, "
    "ownership is renounced, and everything is verifiable on-chain. Keep replies under 240 characters, "
    "match the tweet language, avoid hype or profit promises, and include a polite DYOR reminder when promoting."
)
DEFAULT_CLASSIFICATION_PROMPT = (
    "You triage tweets for the PunkStrategyStrategy ($PSS) outreach bot. Reply only if the tweet is about crypto, "
    "DeFi, on-chain strategy, investment commentary, or community discussions where an educational mention of PSS "
    "adds value. Skip ads, giveaways, unrelated topics, personal complaints, sensitive news, or anything negative "
    "about spam/promotions. Respond with strict JSON: {\"decision\": \"reply|skip\", \"reason\": string, "
    "\"confidence\": number between 0 and 1}. When uncertain, choose skip."
)


@dataclass(slots=True)
class OpenAISettings:
    api_key: Optional[str] = field(default=None, repr=False)
    model: str = DEFAULT_OPENAI_MODEL
    reply_style_prompt: str = DEFAULT_REPLY_PROMPT
    classifier_model: str = DEFAULT_CLASSIFIER_MODEL
    classification_prompt: str = DEFAULT_CLASSIFICATION_PROMPT


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

        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_settings = OpenAISettings(
            api_key=openai_api_key.strip() if openai_api_key else None,
            model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            reply_style_prompt=os.getenv(
                "REPLY_STYLE_PROMPT",
                DEFAULT_REPLY_PROMPT,
            ),
            classifier_model=os.getenv("OPENAI_CLASSIFIER_MODEL", DEFAULT_CLASSIFIER_MODEL),
            classification_prompt=os.getenv(
                "OPENAI_CLASSIFICATION_PROMPT",
                DEFAULT_CLASSIFICATION_PROMPT,
            ),
        )

        poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
        max_tweets = int(os.getenv("MAX_TWEETS_PER_RUN", "10"))
        state_path = "state.json"
        token_store_path = "token_state.json"

        return cls(
            twitter=twitter,
            openai=openai_settings,
            poll_interval_seconds=poll_interval,
            max_tweets_per_run=max_tweets,
            state_path=state_path,
            token_store_path=token_store_path,
        )
