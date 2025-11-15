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
