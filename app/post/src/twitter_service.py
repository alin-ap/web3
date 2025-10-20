"""Twitter API integration using OAuth 2.0 user context tokens."""
from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from typing import Iterable, Optional

import httpx

from .config import TwitterSettings
from .storage import OAuth2Token, Storage


logger = logging.getLogger(__name__)
_API_BASE = "https://api.twitter.com/2"
_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
_DEFAULT_TIMEOUT = httpx.Timeout(timeout=20.0, read=30.0)


@dataclass(slots=True)
class Tweet:
    id: int
    text: str
    author_handle: str
    url: str


class TwitterClient:
    def __init__(self, settings: TwitterSettings, storage: Storage) -> None:
        self._settings = settings
        self._storage = storage
        self._token = storage.load_token()
        if self._token is None:
            self._token = OAuth2Token(
                access_token=settings.access_token,
                refresh_token=settings.refresh_token,
            )
            self._storage.save_token(self._token)
        self._http = httpx.Client(timeout=_DEFAULT_TIMEOUT)

    def fetch_recent_tweets(
        self,
        max_results: int,
        since_id: Optional[int] = None,
    ) -> list[Tweet]:
        max_results = max(1, min(max_results, 100))
        params = {
            "query": self._settings.search_query,
            "max_results": max_results,
            "tweet.fields": "author_id,lang,created_at",
            "expansions": "author_id",
            "user.fields": "username",
        }
        if since_id:
            params["since_id"] = str(since_id)

        response = self._request("GET", f"{_API_BASE}/tweets/search/recent", params=params)
        body = response.json()
        data = body.get("data", [])
        if not data:
            return []

        includes = body.get("includes", {})
        users = {user["id"]: user for user in includes.get("users", [])}
        tweets: list[Tweet] = []
        for item in data:
            author = users.get(item.get("author_id"), {})
            handle = author.get("username", "unknown")
            tweet_id = int(item["id"])
            tweets.append(
                Tweet(
                    id=tweet_id,
                    text=item.get("text", ""),
                    author_handle=handle,
                    url=f"https://twitter.com/{handle}/status/{tweet_id}",
                )
            )
        return tweets

    def post_reply(self, tweet_id: int, text: str) -> None:
        payload = {
            "text": text,
            "reply": {"in_reply_to_tweet_id": str(tweet_id)},
        }
        self._request("POST", f"{_API_BASE}/tweets", json=payload)

    def batch_reply(self, pairs: Iterable[tuple[Tweet, str]]) -> None:
        for tweet, reply in pairs:
            if not reply:
                logger.debug("Skipping empty reply for tweet %s", tweet.id)
                continue
            logger.info("Replying to tweet %s", tweet.url)
            self.post_reply(tweet.id, reply)

    def _request(self, method: str, url: str, *, params=None, json=None) -> httpx.Response:
        response = self._http.request(
            method,
            url,
            params=params,
            json=json,
            headers=self._auth_headers(),
        )
        if response.status_code == 401:
            logger.info("Access token expired, attempting refresh")
            self._refresh_token()
            response = self._http.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._auth_headers(),
            )
        if response.status_code >= 400:
            logger.error(
                "Twitter API error %s: %s", response.status_code, response.text
            )
            response.raise_for_status()
        return response

    def _auth_headers(self) -> dict[str, str]:
        token = self._token
        if token is None or not token.access_token:
            raise RuntimeError("Twitter access token not available")
        return {
            "Authorization": f"Bearer {token.access_token}",
            "Content-Type": "application/json",
        }

    def _refresh_token(self) -> None:
        token = self._token
        if token is None or not token.refresh_token:
            raise RuntimeError("Refresh token not available; cannot refresh access token")

        auth_value = base64.b64encode(
            f"{self._settings.client_id}:{self._settings.client_secret}".encode("utf-8")
        ).decode("ascii")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
        }
        if self._settings.scopes:
            data["scope"] = " ".join(self._settings.scopes)

        response = self._http.post(
            _TOKEN_URL,
            data=data,
            headers={
                "Authorization": f"Basic {auth_value}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if response.status_code >= 400:
            logger.error("Failed to refresh Twitter token: %s", response.text)
            response.raise_for_status()

        payload = response.json()
        expires_in = payload.get("expires_in")
        new_token = OAuth2Token(
            access_token=payload.get("access_token", token.access_token),
            refresh_token=payload.get("refresh_token", token.refresh_token),
            expires_at=(time.time() + float(expires_in)) if expires_in else None,
            scope=payload.get("scope"),
        )
        self._token = new_token
        self._storage.save_token(new_token)
        logger.info("Obtained refreshed access token")
