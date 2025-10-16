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


@dataclass(slots=True)
class ClassificationResult:
    decision: str
    reason: str
    confidence: float

    @property
    def should_reply(self) -> bool:
        return self.decision.lower() == "reply"


class ReplyGenerator:
    def __init__(self, settings: OpenAISettings) -> None:
        self._client = OpenAI(api_key=settings.api_key)
        self._settings = settings

    def should_reply(self, context: TweetContext) -> ClassificationResult:
        """Decide whether the bot should engage with a tweet."""
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
                max_output_tokens=150,
            )
            raw = response.output_text.strip()
            if raw.startswith("```"):
                raw = raw.strip("`").strip()
                if raw.lower().startswith("json"):
                    raw = raw.split("\n", 1)[1] if "\n" in raw else raw[4:]
            data = json.loads(raw)
            decision = str(data.get("decision", "skip")).lower()
            reason = str(data.get("reason", "unable to parse model response"))
            confidence = float(data.get("confidence", 0.0))
        except Exception as exc:  # pragma: no cover - network interaction
            logger.warning("Classification failed for tweet by @%s: %s", context.author_handle, exc)
            decision = "skip"
            reason = "classification_error"
            confidence = 0.0
        return ClassificationResult(decision=decision, reason=reason, confidence=confidence)

    def generate(self, context: TweetContext) -> str:
        """Craft a promotional yet compliant reply for PunkStrategyStrategy."""
        user_prompt = (
            "Compose a concise reply (max 240 characters) that naturally references the tweet while introducing "
            "PunkStrategyStrategy ($PSS). Emphasize the autonomous fee recycling into PNKSTR/ETH liquidity and "
            "buyback/burn loop, renounced ownership, and transparent on-chain execution. Include a soft CTA such as "
            "'check the docs' or 'explore the flywheel', and end with 'DYOR'. Avoid emojis unless present in the "
            "original tweet.\n\n"
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
            max_output_tokens=220,
        )

        return response.output_text.strip()
