"""High-level orchestration of the Twitter auto-reply workflow."""
from __future__ import annotations

import logging
import time
from typing import Optional

from .config import AppSettings
from .openai_service import ReplyGenerator, TweetContext
from .state_store import StateStore
from .token_store import TokenStore
from .twitter_service import Tweet, TwitterClient


logger = logging.getLogger(__name__)


class AutoReplyBot:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._state_store = StateStore(settings.state_path)
        self._token_store = TokenStore(settings.token_store_path)
        self._reply_generator = ReplyGenerator(settings.openai)
        self._twitter = TwitterClient(settings.twitter, self._token_store)

    def run(self) -> None:
        interval = self._settings.poll_interval_seconds
        logger.info("Auto-reply bot started; polling every %s seconds", interval)
        while True:
            replies = self._process_cycle()
            logger.info("Cycle complete. Replies sent: %s", replies)
            logger.info("Sleeping for %s seconds", interval)
            time.sleep(interval)

    def _process_cycle(self) -> int:
        logger.info("Fetching tweets for query %r", self._settings.twitter.search_query)
        state = self._state_store.load()
        tweets = self._twitter.fetch_recent_tweets(
            max_results=self._settings.max_tweets_per_run,
            since_id=state.last_seen_id,
        )
        if not tweets:
            logger.info("No tweets found for query %r", self._settings.twitter.search_query)
            self._state_store.save(state)
            return 0

        tweets.sort(key=lambda tweet: tweet.id)
        processed = set(state.processed_ids)
        replies_sent = 0
        highest_seen_id = state.last_seen_id or 0

        logger.info("Fetched %s tweets", len(tweets))
        for tweet in tweets:
            highest_seen_id = max(highest_seen_id, tweet.id)
            if tweet.id in processed:
                logger.debug("Skipping already processed tweet %s", tweet.id)
                continue
            preview = " ".join(tweet.text.split())
            logger.info("Processing tweet %s by @%s: %s", tweet.id, tweet.author_handle, preview)
            logger.info("Generating reply for tweet %s (@%s)", tweet.id, tweet.author_handle)
            reply = self._build_reply(tweet)
            if not reply:
                continue
            logger.info("Reply content for tweet %s: %s", tweet.id, reply)
            try:
                logger.info("Posting reply to tweet %s", tweet.id)
                self._twitter.post_reply(tweet.id, reply)
            except Exception:  # pragma: no cover - network interaction
                logger.exception("Failed to post reply to tweet %s", tweet.id)
                continue
            processed.add(tweet.id)
            state.processed_ids.append(tweet.id)
            replies_sent += 1

        if highest_seen_id:
            state.last_seen_id = highest_seen_id

        self._state_store.save(state)
        return replies_sent

    def _build_reply(self, tweet: Tweet) -> Optional[str]:
        try:
            draft = self._reply_generator.generate(
                TweetContext(text=tweet.text, author_handle=tweet.author_handle, url=tweet.url)
            )
        except Exception:  # pragma: no cover - network interaction
            logger.exception("Failed to generate reply for tweet %s", tweet.id)
            return None
        cleaned = self._sanitize_reply(draft)
        if not cleaned:
            logger.debug("Generated empty reply for tweet %s", tweet.id)
            return None
        return cleaned

    @staticmethod
    def _sanitize_reply(text: str, limit: int = 280) -> str:
        cleaned = " ".join(text.strip().split())
        if len(cleaned) <= limit:
            return cleaned
        truncated = cleaned[:limit]
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return truncated.strip()
