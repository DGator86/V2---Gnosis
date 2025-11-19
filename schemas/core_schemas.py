from __future__ import annotations

"""Core schemas for the Super Gnosis pipeline."""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


EngineKind = Literal["hedge", "liquidity", "sentiment", "elasticity"]


class EngineOutput(BaseModel):
    """Canonical output of any Engine (Hedge, Liquidity, Sentiment, Elasticity)."""

    kind: EngineKind
    symbol: str
    timestamp: datetime
    features: Dict[str, float]
    confidence: float = Field(ge=0.0, le=1.0)
    regime: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class StandardSnapshot(BaseModel):
    """Canonical fused snapshot consumed by all primary agents."""

    symbol: str
    timestamp: datetime

    hedge: Dict[str, float]
    liquidity: Dict[str, float]
    sentiment: Dict[str, float]
    elasticity: Dict[str, float]

    regime: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


ActionLiteral = Literal["long", "short", "flat", "spread", "complex"]


class Suggestion(BaseModel):
    """Policy-level suggestion produced by agents or the composer."""

    id: str
    layer: str
    symbol: str
    action: ActionLiteral
    confidence: float = Field(ge=0.0, le=1.0)
    forecast: Dict[str, float] = Field(default_factory=dict)
    reasoning: str
    tags: List[str] = Field(default_factory=list)


class TradeLeg(BaseModel):
    """Single leg of a trade idea."""

    instrument_type: Literal["C", "P", "STOCK"]
    direction: Literal["buy", "sell"]
    qty: int
    strike: Optional[float] = None
    expiry: Optional[str] = None


class TradeIdea(BaseModel):
    """Concrete trade object produced by the Trade Agent."""

    id: str
    symbol: str
    strategy_type: str
    side: Literal["long", "short", "neutral"]

    legs: List[TradeLeg]
    cost_per_unit: float
    max_loss: float
    max_profit: Optional[float]
    breakeven_levels: List[float]

    target_exit_price: Optional[float]
    stop_loss_price: Optional[float]
    recommended_units: int

    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    tags: List[str] = Field(default_factory=list)


class LedgerRecord(BaseModel):
    """Single ledger entry tracking a pipeline run."""

    timestamp: datetime
    symbol: str

    snapshot: StandardSnapshot
    primary_suggestions: List[Suggestion]
    composite_suggestion: Suggestion
    trade_ideas: List[TradeIdea]

    realized_pnl: Optional[float] = None


# ============================================================================
# OPTIONS TRADING SCHEMAS
# ============================================================================

class OptionsLeg(BaseModel):
    """Single leg of an options order - Alpaca format"""
    
    symbol: str  # Options symbol in Alpaca format: "AAPL  251219C00250000"
    side: Literal["buy", "sell"]
    quantity: int
    option_type: Literal["call", "put"]
    strike: float
    expiration_date: str  # Format: "YYYY-MM-DD"
    
    # Greeks and pricing (optional, for analysis)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    implied_volatility: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None


class OptionsOrderRequest(BaseModel):
    """Complete options order request for multi-leg strategies"""
    
    order_id: str
    symbol: str  # Underlying symbol
    strategy_name: str  # One of the 28 strategies
    strategy_number: int  # 1-28
    
    legs: List[OptionsLeg]  # 1-4 legs
    
    # Order parameters
    order_type: Literal["market", "limit", "debit", "credit"] = "market"
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"
    limit_price: Optional[float] = None
    
    # Risk parameters
    max_loss: float
    max_profit: Optional[float] = None
    breakeven_points: List[float] = Field(default_factory=list)
    buying_power_reduction: float
    
    # Signal context from Hedge Engine
    hedge_engine_snapshot: Dict[str, float] = Field(default_factory=dict)
    composer_signal: Literal["BUY", "SELL", "HOLD"]
    composer_confidence: float = Field(ge=0.0, le=1.0)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    rationale: str
    tags: List[str] = Field(default_factory=list)


class OptionsPosition(BaseModel):
    """Track an open options position"""
    
    position_id: str
    symbol: str  # Underlying
    strategy_name: str
    legs: List[OptionsLeg]
    
    # Entry details
    entry_date: datetime
    entry_cost: float
    quantity: int  # Number of contracts
    
    # Current status
    current_value: float
    unrealized_pnl: float
    days_in_trade: int
    
    # Exit conditions
    target_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    max_days_held: int = 45
    
    # Hedging status
    is_hedged: bool = False
    hedge_delta: float = 0.0
