"""High-level orchestration of the Twitter auto-reply workflow."""

import logging
import time
from threading import Event
from typing import Optional

from .config import AppSettings
from .openai_service import ReplyGenerator, TweetContext
from .storage import Storage
from .twitter_service import Tweet, TwitterClient


logger = logging.getLogger(__name__)


class AutoReplyBot:
    def __init__(self, settings: AppSettings, dry_run: bool = False) -> None:
        self._settings = settings
        self._storage = Storage(settings.state_path, settings.token_store_path)
        self._dry_run = dry_run
        if settings.openai.api_key:
            self._reply_generator = ReplyGenerator(settings.openai)
        else:
            self._reply_generator = None
            logger.warning(
                "OpenAI API key is not configured; tweets will be logged but no replies will be posted."
            )
        self._twitter = TwitterClient(settings.twitter, self._storage)

    def run(self, stop_event: Optional[Event] = None) -> None:
        interval = self._settings.poll_interval_seconds
        logger.info("Auto-reply bot started; polling every %s seconds", interval)
        if self._dry_run:
            logger.info("Dry run mode enabled; replies will not be posted to Twitter")
        while True:
            if stop_event and stop_event.is_set():
                logger.info("Stop signal received; exiting bot loop")
                return
            replies = self._process_cycle()
            logger.info("Cycle complete. Replies sent: %s", replies)
            logger.info("Sleeping for %s seconds", interval)
            if stop_event:
                if stop_event.wait(interval):
                    logger.info("Stop signal received; exiting bot loop")
                    return
            else:
                time.sleep(interval)

    def _process_cycle(self) -> int:
        logger.info("Fetching tweets for query %r", self._settings.twitter.search_query)
        state = self._storage.load_state()
        tweets = self._twitter.fetch_recent_tweets(
            max_results=self._settings.max_tweets_per_run,
            since_id=state.last_seen_id,
        )
        if not tweets:
            logger.info("No tweets found for query %r", self._settings.twitter.search_query)
            self._storage.save_state(state)
            return 0

        processed = set(state.processed_ids)
        replies_sent = 0
        highest_seen_id = state.last_seen_id or 0

        logger.info("Fetched %s tweets", len(tweets))
        bot_usernames = set(self._settings.twitter.bot_usernames)
        for tweet in tweets:
            highest_seen_id = max(highest_seen_id, tweet.id)
            if tweet.id in processed:
                logger.debug("Skipping already processed tweet %s", tweet.id)
                continue
            if bot_usernames and tweet.author_handle.lower() in bot_usernames:
                logger.debug("Skipping bot-authored tweet %s", tweet.id)
                processed.add(tweet.id)
                state.processed_ids.append(tweet.id)
                continue
            preview = " ".join(tweet.text.split())
            logger.info("Processing tweet %s by @%s: %s", tweet.id, tweet.author_handle, preview)
            if self._reply_generator is None:
                logger.info(
                    "Skipping reply for tweet %s (@%s) because no OpenAI API key is configured.",
                    tweet.id,
                    tweet.author_handle,
                )
                processed.add(tweet.id)
                state.processed_ids.append(tweet.id)
                continue

            should_reply, classifier_note = self._should_reply(tweet)
            if not should_reply:
                logger.info(
                    "Skipping tweet %s (@%s) | classifier=%s",
                    tweet.id,
                    tweet.author_handle,
                    classifier_note,
                )
                processed.add(tweet.id)
                state.processed_ids.append(tweet.id)
                continue

            logger.info(
                "Generating reply for tweet %s (@%s)",
                tweet.id,
                tweet.author_handle,
            )
            reply = self._build_reply(tweet)
            if not reply:
                logger.info("No reply generated for tweet %s", tweet.id)
                processed.add(tweet.id)
                state.processed_ids.append(tweet.id)
                continue
            logger.info("Reply content for tweet %s: %s", tweet.id, reply)
            if self._dry_run:
                logger.info("Dry run enabled; not posting reply for tweet %s", tweet.id)
                processed.add(tweet.id)
                state.processed_ids.append(tweet.id)
                continue
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

        self._storage.save_state(state)
        return replies_sent

    def _build_reply(self, tweet: Tweet) -> Optional[str]:
        if self._reply_generator is None:
            return None
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

    def _should_reply(self, tweet: Tweet) -> tuple[bool, str]:
        if self._reply_generator is None:
            return False, "no_openai_key"
        try:
            context = TweetContext(text=tweet.text, author_handle=tweet.author_handle, url=tweet.url)
            return self._reply_generator.should_reply(context)
        except Exception:  # pragma: no cover - network interaction
            logger.exception("Failed to classify tweet %s", tweet.id)
            return False, "classification_exception"

    @staticmethod
    def _sanitize_reply(text: str, limit: int = 280) -> str:
        cleaned = " ".join(text.strip().split())
        if len(cleaned) <= limit:
            return cleaned
        truncated = cleaned[:limit]
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return truncated.strip()
