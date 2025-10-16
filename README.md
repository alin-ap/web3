# Twitter Auto-Reply Bot

A Python bot that polls the Twitter (X) API for matching tweets, crafts a reply with OpenAI, and posts the response automatically. The bot now uses Twitter's OAuth 2.0 user-context flow, including automatic access-token refresh.

## Features
- Uses the Twitter API v2 search/reply endpoints with OAuth 2.0 tokens.
- Generates on-brand responses with OpenAI's Responses API.
- Persists processed tweet IDs to avoid duplicate replies.
- Refreshes OAuth 2.0 access tokens and stores them locally.
- CLI powered by Typer with single-run or loop modes.
- Environment-driven configuration with `.env` support.

## Prerequisites
- Python 3.11+
- Twitter developer account with OAuth 2.0 user-context enabled (`tweet.read`, `tweet.write`, `users.read`, `offline.access`).
- Initial OAuth 2.0 access token & refresh token (obtained via Authorization Code + PKCE flow). The script handles refresh thereafter.
- OpenAI API key with access to the specified model.

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials. Required keys:
   - `TWITTER_CLIENT_ID`, `TWITTER_CLIENT_SECRET`
   - `TWITTER_REDIRECT_URI` (must match the app callback URL)
   - `TWITTER_ACCESS_TOKEN`, `TWITTER_REFRESH_TOKEN`
   - `OPENAI_API_KEY`
   - `TWITTER_SEARCH_QUERY`

Optional knobs you can tweak:
- `OPENAI_MODEL`, `REPLY_STYLE_PROMPT`
- `POLL_INTERVAL_SECONDS`, `MAX_TWEETS_PER_RUN`
- `STATE_PATH` (processed tweet persistence)
- `TOKEN_STORE_PATH` (where refreshed OAuth tokens are stored)
- `TWITTER_SCOPES` (space-separated list, defaults to `tweet.read tweet.write users.read offline.access`)

## Usage
### Authorize your Twitter account
保持 `.env` 中的 `TWITTER_CLIENT_ID`、`TWITTER_CLIENT_SECRET`、`TWITTER_REDIRECT_URI`、`TWITTER_SCOPES` 为最新值。然后直接运行脚本：

```bash
python -m src.oauth_setup
```

脚本会打印授权链接并等待你在浏览器完成授权，随后提示粘贴回调 URL 中的 `code`。粘贴后回车即可自动换取 `access_token` 与 `refresh_token`，并将结果写入 `token_state.json` 和 `.env`。

### Run the bot
Run a single polling cycle:
```bash
python -m src.main run
```

Run continuously respecting `POLL_INTERVAL_SECONDS`:
```bash
python -m src.main run --loop
```

Pass `--log-level DEBUG` to inspect detailed logs.

## How it works
1. Load configuration, existing state, and cached OAuth tokens from disk.
2. Search for recent tweets matching `TWITTER_SEARCH_QUERY` since the last processed ID.
3. Generate a reply with OpenAI, sanitize to fit within Twitter limits, and post the comment.
4. Persist processed tweet IDs and any refreshed OAuth tokens.

## Testing ideas
- Point `TWITTER_SEARCH_QUERY` to a test account and verify end-to-end behaviour with small batches.
- Mock Twitter/OpenAI clients in unit tests by injecting test doubles into `AutoReplyBot`.
- Run dry runs by commenting out the `post_reply` call while evaluating generated text.



import os, base64, hashlib
verifier = base64.urlsafe_b64encode(os.urandom(64)).decode().rstrip("=")
challenge =base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
print("CODE_VERIFIER=", verifier)
print("CODE_CHALLENGE=", challenge)

CODE_VERIFIER= uePyqApLX-NSo9JJN1glhhS94QlaXYH6ytcsVYFVInwZLkM6v0gZXewjLRNWSj_6F2Is-5MMr2Dw3AccC5CxQA
CODE_CHALLENGE= 7qetxscK-zMdlNoPMLQ1Cx6HCCrZSJBgw5TGR0_Kig0


https://twitter.com/i/oauth2/authorize?response_type=code&client_id=TXhPZ1BfY0UxMEctMmpjTUdkRHU6MTpjaQ&redirect_uri=https%3A%2F%2Fwww.alhpapilot.tech&scope=tweet.read%20tweet.write%20users.read%20offline.access&state=0c8766433f5d294c4f264b7b158e9cc9&code_challenge=7qetxscK-zMdlNoPMLQ1Cx6HCCrZSJBgw5TGR0_Kig0&code_challenge_method=S256
