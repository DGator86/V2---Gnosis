"""
Bar schema for price/volume data.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Bar(BaseModel):
    """OHLCV bar data model."""
    ts: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
