"""
API schemas for Composer endpoints.

Provides clean, API-friendly views of EngineDirective and CompositeMarketDirective.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from agents.composer.schemas import CompositeMarketDirective, EngineDirective


class EngineDirectiveView(BaseModel):
    """
    Lightweight API view of an EngineDirective.
    
    Strips out heavy feature dicts for cleaner HTTP responses.
    """
    engine_name: str = Field(..., description="Engine name: hedge, liquidity, or sentiment")
    direction: float = Field(..., description="Directional bias in [-1, 1]")
    strength: float = Field(..., description="Raw strength score [0, 1]")
    confidence: float = Field(..., description="Engine confidence [0, 1]")
    regime: str = Field(..., description="Current regime label")
    energy: float = Field(..., description="Movement energy/resistance")
    volatility_proxy: Optional[float] = Field(None, description="Volatility proxy if available")
    notes: str = Field(default="", description="Human-readable engine notes")
    feature_count: int = Field(default=0, description="Number of features generated")

    @classmethod
    def from_engine_directive(cls, ed: EngineDirective) -> "EngineDirectiveView":
        """Convert full EngineDirective to API view."""
        return cls(
            engine_name=ed.name,
            direction=ed.direction,
            strength=ed.strength,
            confidence=ed.confidence,
            regime=ed.regime,
            energy=ed.energy,
            volatility_proxy=ed.volatility_proxy,
            notes=ed.notes or "",
            feature_count=len(ed.features),
        )


class ExpectedMoveBandView(BaseModel):
    """API view of expected move band for a specific horizon."""
    horizon_minutes: int
    lower: float
    upper: float
    confidence: float


class ExpectedMoveConeView(BaseModel):
    """API view of expected move cone across multiple horizons."""
    reference_price: float
    bands: Dict[str, ExpectedMoveBandView]


class CompositeDirectiveView(BaseModel):
    """
    API-friendly view of CompositeMarketDirective.
    
    Primary output for trade systems and dashboards.
    """
    direction: int = Field(..., description="Fused direction: -1 (short), 0 (neutral), 1 (long)")
    strength: float = Field(..., description="Strength score [0-100]")
    confidence: float = Field(..., description="Fusion confidence [0-1]")
    volatility: float = Field(..., description="Volatility estimate")
    energy_cost: float = Field(..., description="Total resistance to movement")
    trade_style: str = Field(..., description="momentum, breakout, mean_revert, or no_trade")
    rationale: str = Field(..., description="Human-readable reasoning")
    expected_move_cone: Dict[str, Any] = Field(..., description="Multi-horizon expected move projections")

    @classmethod
    def from_composite_directive(cls, cmd: CompositeMarketDirective) -> "CompositeDirectiveView":
        """Convert full CompositeMarketDirective to API view."""
        return cls(
            direction=cmd.direction,
            strength=cmd.strength,
            confidence=cmd.confidence,
            volatility=cmd.volatility,
            energy_cost=cmd.energy_cost,
            trade_style=cmd.trade_style,
            rationale=cmd.rationale,
            expected_move_cone=cmd.expected_move_cone.model_dump(),
        )


class RegimeWeightsView(BaseModel):
    """Breakdown of regime-based engine weights."""
    hedge: float
    liquidity: float
    sentiment: float
    global_regime: str


class ComposerDirectiveResponse(BaseModel):
    """
    Clean directive-only response.
    
    For consumers that only need the actionable signal.
    """
    symbol: str
    timestamp: str
    composite: CompositeDirectiveView


class ComposerSnapshotResponse(BaseModel):
    """
    Full snapshot: composite + engine directives + weights.
    
    For debugging, analysis, and dashboard visualization.
    """
    symbol: str
    timestamp: str
    composite: CompositeDirectiveView
    engines: Dict[str, EngineDirectiveView]
    regime_weights: Optional[RegimeWeightsView] = None
    raw_features_available: bool = Field(default=False, description="Whether raw features are cached")


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="ok or error")
    version: str = Field(..., description="API version")
    engines_loaded: bool = Field(..., description="Whether engines are initialized")
    message: Optional[str] = Field(None, description="Additional details")
