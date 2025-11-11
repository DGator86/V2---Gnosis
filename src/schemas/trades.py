"""
Trade idea schemas.
"""

from typing import List, Dict, Literal, Union
from datetime import datetime
from pydantic import BaseModel, Field


class TradeIdea(BaseModel):
    """Trade idea with full structure and risk parameters."""
    ts: datetime
    symbol: str
    idea_type: Literal["stock", "options"]
    strategy: str                  # e.g., "call_debit_spread", "iron_condor"
    legs: List[Dict[str, Union[str, float]]]
    entry_cost: float
    exit_target: float
    stop_loss: float
    projected_pnl: float
    recommended_size: int
    ttl_days: float                # time-to-liquidate/expiry
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
