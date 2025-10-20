"""OpenAI helpers for classifying and drafting replies."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from .config import OpenAISettings


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TweetContext:
    text: str
    author_handle: str
    url: Optional[str] = None


class ReplyGenerator:
    def __init__(self, settings: OpenAISettings) -> None:
        self._client = OpenAI(api_key=settings.api_key)
        self._settings = settings

    def should_reply(self, context: TweetContext) -> tuple[bool, str]:
        """Return (should_reply, raw_decision_text)."""
        user_payload = {
            "tweet_author": context.author_handle,
            "tweet_text": context.text.strip(),
        }
        if context.url:
            user_payload["tweet_url"] = context.url

        try:
            response = self._client.responses.create(
                model=self._settings.classifier_model,
                input=[
                    {
                        "role": "system",
                        "content": self._settings.classification_prompt,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False),
                    },
                ],
                max_output_tokens=10000,
            )
            raw = response.output_text.strip()
            if not raw:
                logger.debug(
                    "Classifier raw output empty; treating as reply | payload=%s",
                    response,
                )
                return True, ""
            normalized = raw.strip().upper()
        except Exception as exc:  # pragma: no cover - network interaction
            logger.warning("Classification failed for tweet by @%s: %s", context.author_handle, exc)
            return False, f"error:{exc}"

        if normalized.startswith("SKIP"):
            return False, raw
        return True, raw

    def generate(self, context: TweetContext) -> str:
        """Craft a promotional yet compliant reply for PunkStrategyStrategy."""
        user_prompt = (
            f"Tweet author: @{context.author_handle}\n"
            f"Tweet content: {context.text.strip()}"
        )
        if context.url:
            user_prompt += f"\nTweet URL: {context.url}"

        response = self._client.responses.create(
            model=self._settings.model,
            input=[
                {
                    "role": "system",
                    "content": self._settings.reply_style_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            max_output_tokens=10000,
        )

        logger.debug("Raw reply output for @%s: %r", context.author_handle, response.output_text)

        return response.output_text.strip()
