"""Command-line entry point for the Twitter auto-reply bot."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import typer

from .bot import AutoReplyBot
from .config import AppSettings
from .storage import OAuth2Token, Storage


AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
DEFAULT_SCOPES = ("tweet.read", "tweet.write", "users.read", "offline.access")
_DEFAULT_TIMEOUT = 20.0
_STATE_PATH_DEFAULT = "state.json"
_TOKEN_PATH_DEFAULT = "token_state.json"

app = typer.Typer(add_completion=False)
auth_app = typer.Typer(add_completion=False, help="Twitter OAuth 2.0 helper commands.")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


@app.command()
def run(
    log_level: str = typer.Option("INFO", help="Logging level (DEBUG, INFO, WARNING)."),
    dry_run: bool = typer.Option(
        False,
        help="Generate and log replies without posting to Twitter.",
    ),
) -> None:
    """Start the auto-reply bot in continuous polling mode."""
    configure_logging(log_level)
    settings = AppSettings.from_env()
    bot = AutoReplyBot(settings, dry_run=dry_run)

    typer.echo("Starting auto-reply bot. Press Ctrl+C to stop.")
    try:
        bot.run()
    except KeyboardInterrupt:
        typer.echo("\nStopping bot.")


# ---------------------------------------------------------------------------
# OAuth helper commands
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AuthSettings:
    client_id: str
    client_secret: Optional[str]
    redirect_uri: str
    scopes: tuple[str, ...]
    state: str
    token_path: Path


def generate_code_verifier(length: int = 64) -> str:
    if not 43 <= length <= 128:
        raise ValueError("code_verifier length must be between 43 and 128")
    verifier = base64.urlsafe_b64encode(os.urandom(length)).decode("ascii").rstrip("=")
    if len(verifier) < 43:
        return generate_code_verifier(length + 8)
    return verifier


def code_challenge_from_verifier(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    scope: tuple[str, ...] | list[str] | str,
    state: str,
    code_challenge: str,
) -> str:
    scope_value = scope if isinstance(scope, str) else " ".join(scope)
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope_value,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(query, quote_via=urllib.parse.quote)


def exchange_authorization_code(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    token_url: str = TOKEN_URL,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict[str, str]:
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    with httpx.Client(timeout=httpx.Timeout(timeout, read=timeout)) as client:
        response = client.post(token_url, data=data, headers=headers)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Token exchange failed ({exc.response.status_code}): {exc.response.text}"
        ) from exc
    return response.json()


def _load_auth_settings(require_secret: bool) -> AuthSettings:
    client_id = os.getenv("TWITTER_CLIENT_ID")
    client_secret = os.getenv("TWITTER_CLIENT_SECRET")
    redirect_uri = os.getenv("TWITTER_REDIRECT_URI")
    scopes_env = os.getenv("TWITTER_SCOPES")
    scopes = tuple(filter(None, (scopes_env or " ".join(DEFAULT_SCOPES)).split()))
    state = os.getenv("TWITTER_AUTH_STATE") or secrets.token_hex(16)
    token_path = Path(_TOKEN_PATH_DEFAULT)

    if not client_id or not redirect_uri:
        raise RuntimeError("TWITTER_CLIENT_ID 和 TWITTER_REDIRECT_URI 必须在环境中配置")
    if require_secret and not client_secret:
        raise RuntimeError("缺少 TWITTER_CLIENT_SECRET，无法兑换 token")

    return AuthSettings(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
        state=state,
        token_path=token_path,
    )


def _persist_tokens(
    token_path: Path,
    access_token: Optional[str],
    refresh_token: Optional[str],
    *,
    expires_in: Optional[float],
    scope: Optional[str],
) -> None:
    if not access_token or not refresh_token:
        return
    expires_at = (time.time() + float(expires_in)) if expires_in else None
    storage = Storage(_STATE_PATH_DEFAULT, str(token_path))
    storage.save_token(
        OAuth2Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=scope,
        )
    )
    _update_env_tokens(access_token, refresh_token)


def _update_env_tokens(access_token: Optional[str], refresh_token: Optional[str]) -> None:
    path = Path(".env")
    if not path.exists():
        typer.echo("[info] 未找到 .env，跳过写入。")
        return

    content = path.read_text(encoding="utf-8").splitlines()

    def upsert(lines: list[str], key: str, value: Optional[str]) -> None:
        if value is None:
            return
        prefix = f"{key}="
        for idx, line in enumerate(lines):
            if line.startswith(prefix):
                lines[idx] = prefix + value
                break
        else:
            lines.append(prefix + value)

    upsert(content, "TWITTER_ACCESS_TOKEN", access_token)
    upsert(content, "TWITTER_REFRESH_TOKEN", refresh_token)
    path.write_text("\n".join(content) + "\n", encoding="utf-8")


@auth_app.command("link")
def auth_link(
    state: Optional[str] = typer.Option(None, help="Optional override for OAuth state"),
    code_verifier: Optional[str] = typer.Option(None, help="Provide a code_verifier instead of generating"),
) -> None:
    """Print PKCE parameters and the authorization URL."""
    settings = _load_auth_settings(require_secret=False)
    verifier = code_verifier or generate_code_verifier()
    state_value = state or settings.state
    challenge = code_challenge_from_verifier(verifier)
    url = build_authorization_url(
        client_id=settings.client_id,
        redirect_uri=settings.redirect_uri,
        scope=settings.scopes,
        state=state_value,
        code_challenge=challenge,
    )

    typer.echo(f"CODE_VERIFIER= {verifier}")
    typer.echo(f"CODE_CHALLENGE= {challenge}")
    typer.echo(f"STATE= {state_value}")
    typer.echo("\nAuthorization URL:\n" + url)


@auth_app.command("exchange")
def auth_exchange(
    code: str = typer.Option(..., prompt=True, help="Authorization code returned to the redirect URI"),
    code_verifier: str = typer.Option(..., prompt=True, help="The code_verifier used when generating the link"),
    timeout: float = typer.Option(_DEFAULT_TIMEOUT, help="HTTP timeout in seconds"),
    print_json: bool = typer.Option(False, help="Print the raw JSON payload"),
) -> None:
    """Exchange an authorization code for access and refresh tokens."""
    settings = _load_auth_settings(require_secret=True)
    payload = exchange_authorization_code(
        client_id=settings.client_id,
        client_secret=settings.client_secret or "",
        redirect_uri=settings.redirect_uri,
        code=code,
        code_verifier=code_verifier,
        timeout=timeout,
    )

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    scope = payload.get("scope")

    typer.echo(f"Access token: {access_token}")
    typer.echo(f"Refresh token: {refresh_token}")
    if expires_in:
        typer.echo(f"Expires in (seconds): {expires_in}")
    if scope:
        typer.echo(f"Scope: {scope}")
    if print_json:
        typer.echo("\nPayload:\n" + json.dumps(payload, indent=2))

    _persist_tokens(settings.token_path, access_token, refresh_token, expires_in=expires_in, scope=scope)
    if access_token and refresh_token:
        typer.echo(f"\nTokens saved to {settings.token_path}")
    else:
        typer.echo("\n未收到完整的 access/refresh token，未进行持久化。")


@auth_app.command("walkthrough")
def auth_walkthrough() -> None:
    """Guide the user through generating the link and exchanging tokens interactively."""
    settings = _load_auth_settings(require_secret=True)
    code_verifier = generate_code_verifier()
    code_challenge = code_challenge_from_verifier(code_verifier)
    url = build_authorization_url(
        client_id=settings.client_id,
        redirect_uri=settings.redirect_uri,
        scope=settings.scopes,
        state=settings.state,
        code_challenge=code_challenge,
    )

    typer.echo("请在浏览器中打开以下链接，使用目标账号完成授权：")
    typer.echo(url)
    _ = typer.prompt("授权完成后按 Enter 继续", default="", show_default=False)

    auth_code = typer.prompt("请输入回调 URL 中的 code 值").strip()
    if not auth_code:
        typer.echo("未提供 code，流程已取消。")
        return

    payload = exchange_authorization_code(
        client_id=settings.client_id,
        client_secret=settings.client_secret or "",
        redirect_uri=settings.redirect_uri,
        code=auth_code,
        code_verifier=code_verifier,
    )

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    scope = payload.get("scope")

    typer.echo(f"Access token: {access_token}")
    typer.echo(f"Refresh token: {refresh_token}")

    _persist_tokens(settings.token_path, access_token, refresh_token, expires_in=expires_in, scope=scope)
    if access_token and refresh_token:
        typer.echo(f"已保存到 {settings.token_path}")
    else:
        typer.echo("未成功获取 token；请检查 code 是否正确。")

    typer.echo("流程完成。已经保存 token；如需刷新，请重新运行本命令。")


app.add_typer(auth_app, name="auth")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
