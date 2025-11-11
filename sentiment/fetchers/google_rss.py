"""Google RSS news fetcher."""

import feedparser
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime
from urllib.parse import quote
import logging
import asyncio
from dateutil import parser as date_parser

from .base import NewsFetcher
from ..schemas import NewsDoc

logger = logging.getLogger(__name__)


class GoogleRSSFetcher(NewsFetcher):
    """Fetch news from Google RSS feeds."""
    
    def __init__(self, timeout: int = 10):
        """Initialize fetcher.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
    
    async def fetch(
        self,
        query: str,
        max_articles: int = 10,
        since: Optional[datetime] = None
    ) -> List[NewsDoc]:
        """Fetch news articles from Google RSS.
        
        Args:
            query: Search query
            max_articles: Maximum number of articles
            since: Only fetch articles after this time
            
        Returns:
            List of news documents
        """
        # Run synchronous code in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._fetch_sync,
            query,
            max_articles,
            since
        )
    
    def _fetch_sync(
        self,
        query: str,
        max_articles: int = 10,
        since: Optional[datetime] = None
    ) -> List[NewsDoc]:
        """Synchronous fetch implementation."""
        try:
            rss_url = f"https://news.google.com/rss/search?q={quote(query)}"
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                logger.warning(f"No entries found for query: {query}")
                return []
            
            articles = []
            for entry in feed.entries[:max_articles]:
                try:
                    # Parse published date
                    pub_date = self._parse_date(entry.get('published', ''))
                    
                    # Skip if before cutoff
                    if since and pub_date and pub_date < since:
                        continue
                    
                    # Extract content (simplified)
                    content = self._extract_content(entry.get('link', ''))
                    
                    doc = NewsDoc(
                        id=entry.get('id', entry.get('link', '')),
                        ts_utc=pub_date or datetime.now(),
                        title=entry.get('title', 'No title'),
                        body=content,
                        url=entry.get('link', ''),
                        source=self._extract_source(entry),
                        tickers=[],  # Will be extracted by entity mapper
                        is_pr=self._is_press_release(entry.get('title', '')),
                        lang='en'
                    )
                    articles.append(doc)
                    
                except Exception as e:
                    logger.error(f"Error processing entry: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching RSS feed: {e}")
            return []
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        try:
            return date_parser.parse(date_str)
        except:
            return None
    
    def _extract_source(self, entry: dict) -> str:
        """Extract source from RSS entry."""
        # Google News often includes source in title
        title = entry.get('title', '')
        if ' - ' in title:
            parts = title.rsplit(' - ', 1)
            if len(parts) == 2:
                return parts[1].lower()
        
        return 'unknown'
    
    def _is_press_release(self, title: str) -> bool:
        """Check if article is likely a press release."""
        pr_indicators = [
            'press release',
            'announces',
            'appoints',
            'partners with',
            'launches',
            'introduces'
        ]
        title_lower = title.lower()
        return any(ind in title_lower for ind in pr_indicators)
    
    def _extract_content(self, url: str) -> Optional[str]:
        """Extract article content from URL (simplified)."""
        # In production, you'd want more sophisticated extraction
        # For now, return None to avoid slow scraping
        return None  # Will rely on title for sentiment