"""Wrapper around the OpenAI Responses API for crafting tweet replies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from .config import OpenAISettings


@dataclass(slots=True)
class TweetContext:
    text: str
    author_handle: str
    url: Optional[str] = None


class ReplyGenerator:
    def __init__(self, settings: OpenAISettings) -> None:
        self._client = OpenAI(api_key=settings.api_key)
        self._settings = settings

    def generate(self, context: TweetContext) -> str:
        user_prompt = (
            "You are composing a helpful reply to a tweet. Respond in the first person, "
            "stay under 240 characters, and reference the original tweet naturally.\n\n"
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
            max_output_tokens=200,
        )

        return response.output_text.strip()
