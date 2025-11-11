"""
Signal schemas for agent outputs.
"""

from typing import Dict, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class AgentFinding(BaseModel):
    """Individual agent analysis output."""
    ts: datetime
    symbol: str
    source: Literal["hedge", "liquidity", "sentiment"]
    score: float                   # 0..1 confidence
    notes: str
    features: Dict[str, float]     # explainability breadcrumb
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ComposerOutput(BaseModel):
    """Composer agent synthesis output."""
    ts: datetime
    symbol: str
    direction: Literal["long", "short", "neutral"]
    conviction: float              # 0..1
    horizon_hours: float
    thesis: str
    key_levels: List[float]
    risk_flags: List[str]
    expected_vol: float            # forward vol est
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
