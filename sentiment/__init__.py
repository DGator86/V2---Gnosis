"""Production-ready sentiment engine with FinBERT for financial news analysis."""

from .engine import SentimentEngine
from .schemas import (
    NewsDoc,
    ScoredNews,
    SentimentSpan,
    TickerSentimentSnapshot
)

__version__ = "1.0.0"
__all__ = [
    "SentimentEngine",
    "NewsDoc",
    "ScoredNews",
    "SentimentSpan",
    "TickerSentimentSnapshot"
]