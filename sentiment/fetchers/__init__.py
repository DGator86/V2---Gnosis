"""News fetcher components."""

from .base import NewsFetcher
from .google_rss import GoogleRSSFetcher

__all__ = ["NewsFetcher", "GoogleRSSFetcher"]