# agents/portfolio/schemas.py

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from agents.trade_agent.schemas import StrategyType, TradeIdea


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class Position(BaseModel):
    """
    A live position in the portfolio.
    For v1: treat each position as one TradeIdea 'instance' with size.
    """

    asset: str
    strategy_type: StrategyType
    side: PositionSide = PositionSide.LONG
    size: int = Field(..., ge=0)
    entry_price: float = Field(..., gt=0.0)
    current_price: float = Field(..., gt=0.0)

    max_risk_allocated: float = Field(
        ...,
        description="Capital initially allocated as maximum loss for this position.",
    )
    unrealized_pnl: float = 0.0


class PortfolioState(BaseModel):
    """
    Snapshot of current portfolio state. Stateless consumer will be given this.
    """

    equity: float = Field(..., ge=0.0)  # Allow zero for edge case testing
    cash: float = Field(..., ge=0.0)
    positions: List[Position] = Field(default_factory=list)


class OrderAction(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    ADJUST = "adjust"


class OrderInstruction(BaseModel):
    """
    Instruction to change portfolio state.
    v1 focuses on 'open' orders from new trade ideas.
    """

    action: OrderAction
    asset: str
    strategy_type: StrategyType
    size_delta: int = Field(..., description="Positive to increase, negative to reduce.")
    notional_risk: float = Field(
        ...,
        description="Capital intended to be put at risk (matches idea.max_risk where possible).",
    )
    reason: str
    source_idea: Optional[TradeIdea] = None
