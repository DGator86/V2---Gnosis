from __future__ import annotations

"""News adapter interface."""

from datetime import datetime
from typing import Dict, List, Protocol


class NewsAdapter(Protocol):
    """Protocol describing a news data provider."""

    def fetch_news(self, symbol: str, lookback_hours: int, now: datetime) -> List[Dict[str, str]]:
        """Return a list of news items for ``symbol``."""

        raise NotImplementedError
