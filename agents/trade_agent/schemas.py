# agents/trade_agent/schemas.py

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ExpectedMove(str, Enum):
    TINY = "tiny"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXPLOSIVE = "explosive"


class VolatilityRegime(str, Enum):
    LOW = "low_vol"
    MID = "mid_vol"
    HIGH = "high_vol"
    VOL_CRUSH = "vol_crush_expected"
    VOL_EXPANSION = "vol_expansion_expected"


class Timeframe(str, Enum):
    INTRADAY = "intraday"
    SWING = "swing"
    POSITIONAL = "positional"


class StrategyType(str, Enum):
    STOCK = "stock"
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    CALL_DEBIT_SPREAD = "call_debit_spread"
    PUT_DEBIT_SPREAD = "put_debit_spread"
    IRON_CONDOR = "iron_condor"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    BROKEN_WING_BUTTERFLY = "broken_wing_butterfly"
    SYNTHETIC_LONG = "synthetic_long"
    SYNTHETIC_SHORT = "synthetic_short"
    REVERSE_IRON_CONDOR = "reverse_iron_condor"


class OptionLeg(BaseModel):
    """
    Represents a single option leg in a multi-leg strategy.
    """

    side: Literal["long", "short"]
    option_type: Literal["call", "put"]
    strike: float
    expiry: str  # ISO date string e.g. "2025-08-15"
    quantity: int = 1
    estimated_price: Optional[float] = None  # per contract


class StrategyGreeks(BaseModel):
    """
    Coarse Greeks exposure summary for the overall strategy.
    """

    delta: float
    gamma: float
    theta: float
    vega: float


class TradeIdea(BaseModel):
    """
    Canonical representation of a trade idea returned by the Trade Agent.
    """

    asset: str
    strategy_type: StrategyType
    description: str

    # Structure
    legs: List[OptionLeg] = Field(default_factory=list)

    # Economics
    total_cost: Optional[float] = None
    max_risk: Optional[float] = None
    max_profit: Optional[float] = None

    # Risk management
    recommended_size: Optional[int] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None

    # Meta
    timeframe: Optional[Timeframe] = None
    confidence: float = 0.0
    ranking_score: Optional[float] = None
    greeks_profile: Optional[StrategyGreeks] = None
    notes: Optional[str] = None


class ComposerTradeContext(BaseModel):
    """
    Adapter-normalized context derived from CompositeMarketDirective.
    This is the canonical 'signal' view consumed by the Trade Agent.
    """

    asset: str
    direction: Direction
    confidence: float = Field(ge=0.0, le=1.0)
    expected_move: ExpectedMove
    volatility_regime: VolatilityRegime
    timeframe: Timeframe

    # Field / Greeks meta
    elastic_energy: float = Field(
        description="Internal 'energy cost' scalar for moving price."
    )
    gamma_exposure: float
    vanna_exposure: float
    charm_exposure: float
    liquidity_score: float = Field(
        description="0–1 score, 1 = ideal liquidity."
    )
