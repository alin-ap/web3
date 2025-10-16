"""OAuth-related utilities for the Twitter auto-reply bot."""

from .twitter_auth import main  # re-export CLI entrypoint

__all__ = ["main"]
