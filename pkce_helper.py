"""Utilities for completing the Twitter OAuth2 PKCE exchange."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.parse

import httpx

from src.token_store import OAuth2Token, TokenStore

AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
DEFAULT_SCOPE = "tweet.read tweet.write users.read offline.access"
DEFAULT_CLIENT_ID = "TXhPZ1BfY0UxMEctMmpjTUdkRHU6MTpjaQ"
DEFAULT_REDIRECT_URI = "https://www.punkstrategystrategy.com"

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
    scope: str,
    state: str,
    code_challenge: str,
) -> str:
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(query, quote_via=urllib.parse.quote)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-id",
        default=os.getenv("TWITTER_CLIENT_ID", DEFAULT_CLIENT_ID),
        help="Twitter OAuth2 client ID",
    )
    parser.add_argument(
        "--client-secret",
        default=os.getenv("TWITTER_CLIENT_SECRET"),
        help="Twitter OAuth2 client secret (required for code exchange)",
    )
    parser.add_argument(
        "--redirect-uri",
        default=os.getenv("TWITTER_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        help="Configured callback URL",
    )
    parser.add_argument(
        "--scope",
        default=os.getenv("TWITTER_SCOPES", DEFAULT_SCOPE),
        help="Space separated scope list",
    )
    parser.add_argument(
        "--code-verifier",
        help="Existing code_verifier; generated if omitted",
    )
    parser.add_argument(
        "--state",
        help="Optional state value; random hex is generated if omitted",
    )
    parser.add_argument(
        "--authorization-code",
        help="Authorization code returned to the redirect URI",
    )
    parser.add_argument(
        "--token-url",
        default=TOKEN_URL,
        help="Override the token endpoint (default: %(default)s)",
    )
    parser.add_argument(
        "--save-path",
        default=os.getenv("TOKEN_STORE_PATH", "token_state.json"),
        help="Path to persist the resulting tokens (default: %(default)s)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip writing tokens to disk",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print the raw JSON payload returned by Twitter",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds for token exchange",
    )
    return parser.parse_args(argv)


def exchange_authorization_code(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    token_url: str,
    timeout: float,
) -> dict[str, str]:
    auth_value = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }
    headers = {
        "Authorization": f"Basic {auth_value}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    with httpx.Client(timeout=httpx.Timeout(timeout, read=timeout)) as client:
        response = client.post(token_url, data=data, headers=headers)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(
            f"Token exchange failed ({exc.response.status_code}): {exc.response.text}"
        ) from exc
    return response.json()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    exchanging = bool(args.authorization_code)

    if exchanging and not args.code_verifier:
        raise SystemExit("--code-verifier is required when supplying --authorization-code")
    if exchanging and not args.client_secret:
        raise SystemExit("--client-secret (or TWITTER_CLIENT_SECRET) is required for token exchange")

    code_verifier = args.code_verifier or generate_code_verifier()
    code_challenge = code_challenge_from_verifier(code_verifier)

    if not exchanging:
        state = args.state or secrets.token_hex(16)
        url = build_authorization_url(
            client_id=args.client_id,
            redirect_uri=args.redirect_uri,
            scope=args.scope,
            state=state,
            code_challenge=code_challenge,
        )

        print("CODE_VERIFIER=", code_verifier)
        print("CODE_CHALLENGE=", code_challenge)
        print("STATE=", state)
        print("\nAuthorization URL:\n", url)

    if exchanging:
        payload = exchange_authorization_code(
            client_id=args.client_id,
            client_secret=args.client_secret,
            redirect_uri=args.redirect_uri,
            code=args.authorization_code,
            code_verifier=code_verifier,
            token_url=args.token_url,
            timeout=args.timeout,
        )
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        scope = payload.get("scope")

        print("\nAccess token:", access_token)
        print("Refresh token:", refresh_token)
        if expires_in:
            print("Expires in (seconds):", expires_in)
        if scope:
            print("Scope:", scope)
        if args.print_json:
            print("\nFull payload:\n", json.dumps(payload, indent=2))

        if not args.no_save and access_token and refresh_token:
            expires_at = (time.time() + float(expires_in)) if expires_in else None
            token = OAuth2Token(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=scope,
            )
            TokenStore(args.save_path).save(token)
            print(f"\nTokens saved to {args.save_path}")
        elif args.no_save:
            print("\nSkipping token persistence (--no-save supplied)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
