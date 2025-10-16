"""Command-line entry point for the Twitter auto-reply bot."""
from __future__ import annotations

import logging
import sys

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
    log_level: str = typer.Option("INFO", help="Logging level (DEBUG, INFO, WARNING)."),
) -> None:
    """Start the auto-reply bot in continuous polling mode."""
    configure_logging(log_level)
    settings = AppSettings.from_env()
    bot = AutoReplyBot(settings)

    typer.echo("Starting auto-reply bot. Press Ctrl+C to stop.")
    try:
        bot.run()
    except KeyboardInterrupt:
        typer.echo("\nStopping bot.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
