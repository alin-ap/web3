"""Simplified helper to obtain Twitter OAuth2 tokens with minimal steps."""
from __future__ import annotations

import os
import time
from pathlib import Path
import re

from dotenv import load_dotenv

from pkce_helper import (
    build_authorization_url,
    code_challenge_from_verifier,
    generate_code_verifier,
    exchange_authorization_code,
)
from src.token_store import OAuth2Token, TokenStore

# Load .env values so the flow uses the same configuration as the bot.
load_dotenv()

CLIENT_ID = os.getenv("TWITTER_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITTER_CLIENT_SECRET")
REDIRECT_URI = os.getenv("TWITTER_REDIRECT_URI")
SCOPES = os.getenv(
    "TWITTER_SCOPES",
    "tweet.read tweet.write users.read offline.access",
)
TOKEN_PATH = os.getenv("TOKEN_STORE_PATH", "token_state.json")


def run_authorization_flow() -> None:
    """Generate authorization URL and exchange code via a single guided flow."""
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise RuntimeError(
            "请先在 .env 中填写 TWITTER_CLIENT_ID/TWITTER_CLIENT_SECRET/TWITTER_REDIRECT_URI"
        )

    code_verifier = generate_code_verifier()
    code_challenge = code_challenge_from_verifier(code_verifier)
    auth_url = build_authorization_url(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        state=os.getenv("TWITTER_AUTH_STATE", "state-token"),
        code_challenge=code_challenge,
    )

    print("请在浏览器中打开以下链接，使用目标账号完成授权：")
    print(auth_url)
    input("授权完成后按 Enter 继续...")
    auth_code = input("请输入回调 URL 中的 code 值: ").strip()
    if not auth_code:
        print("未提供 code，流程已取消。")
        return

    payload = exchange_authorization_code(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        code=auth_code,
        code_verifier=code_verifier,
        token_url="https://api.twitter.com/2/oauth2/token",
        timeout=20.0,
    )

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    scope = payload.get("scope")

    print("access_token:", access_token)
    print("refresh_token:", refresh_token)

    if access_token and refresh_token:
        expires_at = (time.time() + float(expires_in)) if expires_in else None
        TokenStore(TOKEN_PATH).save(
            OAuth2Token(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=scope,
            )
        )
        print(f"已保存到 {TOKEN_PATH}")

        _update_env_tokens(access_token, refresh_token)

    print("流程完成。已经保存 token；如需刷新，请重新运行本脚本。")


def _update_env_tokens(access_token: str | None, refresh_token: str | None) -> None:
    path = Path(".env")
    if not path.exists():
        print("未找到 .env，跳过写入。")
        return

    content = path.read_text(encoding="utf-8").splitlines()
    filtered = [
        line
        for line in content
        if not re.match(r"^(TWITTER_(AUTH_CODE|CODE_VERIFIER))=", line)
    ]

    def upsert(lines: list[str], key: str, value: str | None) -> None:
        if value is None:
            return
        pattern = re.compile(rf"^{re.escape(key)}=")
        for idx, line in enumerate(lines):
            if pattern.match(line):
                lines[idx] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")

    upsert(filtered, "TWITTER_ACCESS_TOKEN", access_token)
    upsert(filtered, "TWITTER_REFRESH_TOKEN", refresh_token)

    path.write_text("\n".join(filtered) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run_authorization_flow()
