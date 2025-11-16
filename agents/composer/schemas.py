# agents/composer/schemas.py

from typing import Dict, Optional, Literal, Any
from pydantic import BaseModel, Field


Direction = Literal[-1, 0, 1]


class EngineDirective(BaseModel):
    """
    Normalized directive from any engine agent (hedge, liquidity, sentiment).

    This is the common format the Composer consumes.
    """
    name: str = Field(..., description="Engine name: 'hedge', 'liquidity', 'sentiment'.")
    direction: float = Field(..., description="Bias direction in [-1, 1].")
    strength: float = Field(..., ge=0.0, description="Raw engine strength score.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Engine confidence in [0,1].")
    regime: str = Field(..., description="Engine-specific regime label.")
    energy: float = Field(0.0, description="Energy/resistance score; higher = harder move.")
    volatility_proxy: Optional[float] = Field(
        None, description="Optional volatility proxy from engine (e.g., IV, realized vol)."
    )
    features: Dict[str, float] = Field(
        default_factory=dict,
        description="Namespace-prefixed features ready for fusion, e.g. 'hedge_gamma', 'liq_kyle_lambda'.",
    )
    notes: Optional[str] = Field(
        None, description="Human-readable notes or rationale from engine agent."
    )


class ExpectedMoveBand(BaseModel):
    """
    Simple representation of an expected move band for a given horizon.
    """
    horizon_minutes: int
    lower: float
    upper: float
    confidence: float


class ExpectedMoveCone(BaseModel):
    """
    Aggregated cone for multiple horizons.
    """
    reference_price: float
    bands: Dict[str, ExpectedMoveBand]  # e.g. '15m', '1h', '1d'


class CompositeMarketDirective(BaseModel):
    """
    Final output of the Composer Agent.

    This is what the Trade Agent consumes.
    """
    direction: Direction
    strength: float  # 0–100 scaled strength
    confidence: float  # 0–1
    volatility: float  # generic volatility level (e.g. 0–100)
    energy_cost: float  # total resistance; higher = harder to move
    trade_style: str  # e.g. 'momentum', 'mean_revert', 'breakout', 'no_trade'
    expected_move_cone: ExpectedMoveCone
    rationale: str

    # Optional raw engine snapshot for debugging / inspection
    raw_engines: Optional[Dict[str, Any]] = None
