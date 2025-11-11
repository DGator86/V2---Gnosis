"""Base class for news fetchers."""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from ..schemas import NewsDoc


class NewsFetcher(ABC):
    """Abstract base class for news fetchers."""
    
    @abstractmethod
    async def fetch(
        self,
        query: str,
        max_articles: int = 10,
        since: Optional[datetime] = None
    ) -> List[NewsDoc]:
        """Fetch news articles.
        
        Args:
            query: Search query
            max_articles: Maximum number of articles
            since: Only fetch articles after this time
            
        Returns:
            List of news documents
        """
        pass