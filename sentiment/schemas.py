"""Pydantic schemas for sentiment engine data structures."""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SentimentLabel(str, Enum):
    """Sentiment classification labels."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class NewsDoc(BaseModel):
    """Represents a news article document."""
    id: str
    ts_utc: datetime
    title: str
    body: Optional[str] = None
    url: str
    source: str
    tickers: List[str] = Field(default_factory=list)
    is_pr: bool = False
    novelty_hash: Optional[str] = None
    lang: str = "en"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('source')
    @classmethod
    def lowercase_source(cls, v: str) -> str:
        return v.lower()


class SentimentSpan(BaseModel):
    """Sentiment analysis result for a specific ticker."""
    ticker: str
    label: SentimentLabel
    score: float = Field(ge=-1.0, le=1.0)  # Signed score in [-1, 1]
    probs: Dict[str, float]  # {"pos": ..., "neu": ..., "neg": ...}
    model: str = "ProsusAI/finbert"
    confidence: float = Field(ge=0.0, le=1.0)
    

class ScoredNews(BaseModel):
    """News document with sentiment scores."""
    doc: NewsDoc
    spans: List[SentimentSpan]
    processing_time_ms: Optional[float] = None


class TickerSentimentSnapshot(BaseModel):
    """Complete sentiment snapshot for a ticker at a specific time window."""
    ticker: str
    window: str  # "5m", "30m", "1h", "1d"
    n_docs: int = Field(ge=0)
    
    # Core statistics
    mean: float = Field(ge=-1.0, le=1.0)
    std: float = Field(ge=0.0)
    skew: float
    
    # Advanced metrics
    disagreement: float = Field(ge=0.0, le=1.0)
    momentum: float = Field(ge=-1.0, le=1.0)
    surprise: float
    novelty: float = Field(ge=0.0, le=1.0)
    source_weighted_mean: float = Field(ge=-1.0, le=1.0)
    entropy: float = Field(ge=0.0, le=1.0)
    sharpe_like: float
    
    # Correlations
    corr_to_market: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    corr_to_ref: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    ref_name: Optional[str] = None
    
    # Convenience flags for trading decisions
    is_contrarian_market: Optional[bool] = None
    is_contrarian_sector: Optional[bool] = None
    is_strong_contrarian: Optional[bool] = None
    is_trending_sentiment: Optional[bool] = None
    is_information_shock: Optional[bool] = None
    
    # Metadata
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }