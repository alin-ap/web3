"""Command-line entry point for the Twitter auto-reply bot."""
from __future__ import annotations

import logging
import sys
from typing import Optional

import typer

from .bot import AutoReplyBot
from .config import AppSettings


app = typer.Typer(add_completion=False)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


@app.command()
def run(
    loop: bool = typer.Option(
        False,
        help="Keep running on an interval defined by POLL_INTERVAL_SECONDS.",
    ),
    log_level: str = typer.Option("INFO", help="Logging level (DEBUG, INFO, WARNING)."),
) -> None:
    """Execute the auto-reply workflow once or continuously."""
    configure_logging(log_level)
    settings = AppSettings.from_env()
    bot = AutoReplyBot(settings)

    if loop:
        typer.echo("Starting auto-reply bot in continuous mode. Press Ctrl+C to stop.")
        try:
            bot.run_forever()
        except KeyboardInterrupt:
            typer.echo("\nStopping bot.")
    else:
        replies = bot.run_once()
        typer.echo(f"Replies sent: {replies}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
