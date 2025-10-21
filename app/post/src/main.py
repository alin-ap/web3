"""Command-line entry point for the Twitter auto-reply bot."""

import base64
import hashlib
import json
import logging
import os
import secrets
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import typer

from .bot import AutoReplyBot
from .config import AppSettings, BOTS_CONFIG, token_cache_path
from .storage import OAuth2Token, Storage


AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
DEFAULT_SCOPES = ("tweet.read", "tweet.write", "users.read", "offline.access")
_DEFAULT_TIMEOUT = 20.0
_VAR_DIR = Path(__file__).resolve().parent.parent / "var"
_STATE_PATH_DEFAULT = str(_VAR_DIR / "state.json")

app = typer.Typer(add_completion=False)
auth_app = typer.Typer(add_completion=False, help="Twitter OAuth 2.0 helper commands.")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
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
    handle: Optional[str] = typer.Option(None, help="Override config.yml account handle for this run."),
) -> None:
    """Start the auto-reply bot in continuous polling mode."""
    configure_logging(log_level)
    handle_value = handle.lstrip("@") if handle else None
    settings = AppSettings.from_env(handle=handle_value)
    bot = AutoReplyBot(settings, dry_run=dry_run)

    typer.echo("Starting auto-reply bot. Press Ctrl+C to stop.")
    try:
        bot.run()
    except KeyboardInterrupt:
        typer.echo("\nStopping bot.")


def _normalize_handle(value: str) -> str:
    return value.strip().lstrip("@")


def _run_bot_worker(handle: str, bot: AutoReplyBot, stop_event: threading.Event) -> None:
    try:
        bot.run(stop_event=stop_event)
    except Exception:  # pragma: no cover - network interaction / thread
        logging.getLogger(__name__).exception("Bot thread for handle %s crashed", handle)


@app.command("run-all")
def run_all(
    log_level: str = typer.Option("INFO", help="Logging level (DEBUG, INFO, WARNING)."),
    dry_run: bool = typer.Option(
        False,
        help="Generate and log replies without posting to Twitter.",
    ),
    handle: Optional[list[str]] = typer.Option(
        None,
        "--handle",
        help="Limit to the specified handles (can be provided multiple times).",
    ),
) -> None:
    """Start auto-reply bots for multiple accounts concurrently."""
    configure_logging(log_level)
    if BOTS_CONFIG is None:
        raise RuntimeError("缺少 config.yml，无法加载账号配置")

    if handle:
        handles_normalized: list[str] = []
        for item in handle:
            normalized = _normalize_handle(item)
            if not normalized:
                raise typer.BadParameter(f"无效的 handle 值: {item!r}")
            try:
                account = BOTS_CONFIG.accounts[normalized.lower()]
            except KeyError as exc:
                raise typer.BadParameter(f"config.yml 未找到 handle={item} 的账号配置") from exc
            handles_normalized.append(account.handle)
    else:
        handles_normalized = [account.handle for account in BOTS_CONFIG.accounts.values()]

    if not handles_normalized:
        raise RuntimeError("config.yml 中没有配置任何账号")

    stop_events: list[threading.Event] = []
    threads: list[threading.Thread] = []

    for account_handle in handles_normalized:
        stop_event = threading.Event()
        handle_key = _normalize_handle(account_handle)
        settings = AppSettings.from_env(handle=handle_key)
        bot = AutoReplyBot(settings, dry_run=dry_run)
        thread = threading.Thread(
            target=_run_bot_worker,
            name=f"bot-{handle_key}",
            args=(account_handle, bot, stop_event),
            daemon=True,
        )
        stop_events.append(stop_event)
        threads.append(thread)
        thread.start()
        typer.echo(f"Started bot for @{handle_key}")

    typer.echo("All bots running. Press Ctrl+C to stop.")
    try:
        while True:
            if not any(thread.is_alive() for thread in threads):
                typer.echo("All bot threads have exited.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("\nStop signal received. Shutting down bots...")
    finally:
        for event in stop_events:
            event.set()
        for thread in threads:
            thread.join()
    typer.echo("All bots stopped.")


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


def _resolve_handle(handle: Optional[str]) -> str:
    if handle:
        return handle.lstrip("@").strip()
    env_handle = os.getenv("TWITTER_HANDLE")
    if env_handle:
        return env_handle.lstrip("@").strip()
    if BOTS_CONFIG is None:
        raise RuntimeError("缺少 config.yml，无法确定默认 handle")
    return BOTS_CONFIG.select_account(None).handle


def _load_auth_settings(require_secret: bool, *, handle: Optional[str]) -> AuthSettings:
    client_id = os.getenv("TWITTER_CLIENT_ID")
    client_secret = os.getenv("TWITTER_CLIENT_SECRET")
    redirect_uri = os.getenv("TWITTER_REDIRECT_URI")
    scopes_env = os.getenv("TWITTER_SCOPES")
    scopes = tuple(filter(None, (scopes_env or " ".join(DEFAULT_SCOPES)).split()))
    state = os.getenv("TWITTER_AUTH_STATE") or secrets.token_hex(16)
    resolved_handle = _resolve_handle(handle)
    if not resolved_handle:
        raise RuntimeError("缺少 handle，无法确定 token 存储路径")
    token_path = token_cache_path(resolved_handle)

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


@auth_app.command("link")
def auth_link(
    handle: Optional[str] = typer.Option(None, help="目标 Twitter handle（无需 @）"),
    state: Optional[str] = typer.Option(None, help="Optional override for OAuth state"),
    code_verifier: Optional[str] = typer.Option(None, help="Provide a code_verifier instead of generating"),
) -> None:
    """Print PKCE parameters and the authorization URL."""
    settings = _load_auth_settings(require_secret=False, handle=handle)
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
    handle: Optional[str] = typer.Option(None, help="目标 Twitter handle（无需 @）"),
    code: str = typer.Option(..., prompt=True, help="Authorization code returned to the redirect URI"),
    code_verifier: str = typer.Option(..., prompt=True, help="The code_verifier used when generating the link"),
    timeout: float = typer.Option(_DEFAULT_TIMEOUT, help="HTTP timeout in seconds"),
    print_json: bool = typer.Option(False, help="Print the raw JSON payload"),
) -> None:
    """Exchange an authorization code for access and refresh tokens."""
    settings = _load_auth_settings(require_secret=True, handle=handle)
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
        typer.echo("记得把最新的 access/refresh token 同步回 config.yml。")
    else:
        typer.echo("\n未收到完整的 access/refresh token，请重试。")


@auth_app.command("walkthrough")
def auth_walkthrough(
    handle: Optional[str] = typer.Option(None, help="目标 Twitter handle（无需 @）")
) -> None:
    """Guide the user through generating the link and exchanging tokens interactively."""
    settings = _load_auth_settings(require_secret=True, handle=handle)
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
        typer.echo("请同步更新 config.yml 内对应账号的 token。")
    else:
        typer.echo("未成功获取 token；请检查 code 是否正确。")


app.add_typer(auth_app, name="auth")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
