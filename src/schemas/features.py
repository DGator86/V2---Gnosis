"""
Feature schemas for engine outputs.
"""

from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class HedgeFields(BaseModel):
    """Dealer hedge pressure fields output."""
    ts: datetime
    symbol: str
    gex: float            # aggregate gamma exposure
    vanna: float
    charm: float
    gamma_flip_level: Optional[float] = None
    pressure_score: float # normalized 0..1 (magnitude of "dealer field")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LiquidityFields(BaseModel):
    """Liquidity and dark pool metrics output."""
    ts: datetime
    symbol: str
    amihud: float
    kyle_lambda: float
    vpoc: float           # volume point of control
    zones: List[float]    # key supply/demand levels
    dark_pool_ratio: Optional[float] = None
    liquidity_trend: Literal["tightening", "loosening", "neutral"]
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SentimentFields(BaseModel):
    """Sentiment and regime analysis output."""
    ts: datetime
    symbol: str
    news_sentiment: float        # -1..1
    social_sentiment: Optional[float] = None
    regime: Literal["calm", "normal", "elevated", "squeeze_risk", "gamma_storm", "unknown"]
    wyckoff_phase: Literal["accumulation", "markup", "distribution", "markdown", "unknown"]
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EngineSnapshot(BaseModel):
    """Combined snapshot from all engines."""
    ts: datetime
    symbol: str
    hedge: HedgeFields
    liquidity: LiquidityFields
    sentiment: SentimentFields
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
