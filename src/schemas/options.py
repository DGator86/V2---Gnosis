"""
Options snapshot schema.
"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class OptionSnapshot(BaseModel):
    """Options market data snapshot."""
    ts: datetime
    symbol: str           # underlying
    expiry: str
    strike: float
    right: Literal["C", "P"]
    bid: float
    ask: float
    iv: float
    delta: float
    gamma: float
    vega: float
    theta: float
    open_interest: Optional[int] = None
    volume: Optional[int] = None
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
