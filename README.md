# Twitter Auto-Reply Bot

A Python bot that polls the Twitter (X) API for matching tweets, crafts a reply with OpenAI, and posts the response automatically. The bot uses Twitter's OAuth 2.0 user-context flow (Authorization Code + PKCE) and automatically refreshes access tokens.

## Features
- Twitter API v2 search/reply powered by OAuth 2.0 tokens.
- On-brand responses generated via OpenAI's Responses API.
- Deduplication of processed tweets to avoid double replies.
- Automatic refresh-token handling with local persistence.
- Typer-based CLI for continuous polling.
- Environment-driven configuration with optional `.env` file.

## Prerequisites
- Python 3.11+
- Twitter developer account with OAuth 2.0 user-context enabled (`tweet.read`, `tweet.write`, `users.read`, `offline.access`).
- OpenAI API key with access to the configured model.

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in required credentials:
   - `TWITTER_CLIENT_ID`, `TWITTER_CLIENT_SECRET`
   - `TWITTER_REDIRECT_URI` (must match the app callback URL)
   - `OPENAI_API_KEY`
   - `TWITTER_SEARCH_QUERY`

Optional knobs include `OPENAI_MODEL`, `REPLY_STYLE_PROMPT`, `POLL_INTERVAL_SECONDS`, `MAX_TWEETS_PER_RUN`, `STATE_PATH`, `TOKEN_STORE_PATH`, and `TWITTER_SCOPES` (space-separated).

## Authorize your Twitter account
Keep the `.env` values for Twitter credentials in sync. Then run the guided OAuth utility:

```bash
python -m src.oauth.twitter_auth walkthrough
```

The command prints an authorization link, waits for you to approve access in the browser, and exchanges the returned `code` for `access_token` and `refresh_token`. Tokens are saved to `token_state.json` (or the path from `TOKEN_STORE_PATH`) and `.env`.

Alternative commands:
- `python -m src.oauth.twitter_auth link`  Generate PKCE parameters and the authorization URL only.
- `python -m src.oauth.twitter_auth exchange --code <code> --code-verifier <verifier>`  Manually exchange an authorization code.

## Run the bot
Start the continuous loop (respects `POLL_INTERVAL_SECONDS`, press `Ctrl+C` to stop):
```bash
python -m src.main run
```

Add `--log-level DEBUG` for verbose logs.

## How it works
1. Load configuration, existing state, and cached OAuth tokens from disk.
2. Search recent tweets matching `TWITTER_SEARCH_QUERY` since the last processed ID.
3. Generate a reply with OpenAI, sanitize it, and post the response.
4. Persist processed tweet IDs and refreshed OAuth tokens.

## src 目录说明
- `src/__init__.py` 包初始化文件，让 `src` 目录可以以包形式被引用。
- `src/main.py` Typer 命令行入口，负责解析参数并触发机器人运行模式。
- `src/bot.py` 机器人核心流程：拉取推文、调用 OpenAI 回复、发送并记录状态。
- `src/config.py` 读取 `.env` 与环境变量，构建 Twitter 与 OpenAI 的配置对象。
- `src/openai_service.py` 与 OpenAI API 交互，根据推文上下文生成合适回复。
- `src/state_store.py` 持久化已处理推文 ID 与最新查询位置，防止重复回复。
- `src/token_store.py` 定义 OAuth2Token 数据结构并负责 access/refresh token 的本地读写。
- `src/twitter_service.py` 封装 Twitter API 调用，管理搜索、回复与令牌刷新逻辑。
- `src/oauth/twitter_auth.py` OAuth 授权工具，提供生成链接、换取令牌以及引导式流程的 CLI。

## Testing ideas
- Target a test account via `TWITTER_SEARCH_QUERY` to verify end-to-end behaviour.
- Mock Twitter/OpenAI clients in unit tests by injecting test doubles into `AutoReplyBot`.
- Perform dry runs by commenting out `post_reply` while evaluating generated text.
