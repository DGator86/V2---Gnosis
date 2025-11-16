"""
Hedge Agent Schemas - Canonical v3.0

Input/Output schemas for the Hedge Agent pure interpretation layer.
The Hedge Agent does NOT compute Greeks or pressure fields.
It ONLY interprets pre-computed Hedge Engine outputs.
"""

from typing import Dict, List

from pydantic import BaseModel, Field


class HedgeAgentInput(BaseModel):
    """
    Input schema for Hedge Agent interpretation.
    
    All fields are pre-computed by the Hedge Engine.
    The agent performs ZERO computation - pure interpretation only.
    
    Attributes:
        net_pressure: Net directional pressure from all Greek fields
        pressure_mtf: Multi-timeframe pressure breakdown
        gamma_curvature: Gamma-based price elasticity (curvature term)
        vanna_drift: Vanna-induced drift from vol changes
        charm_decay: Time decay pressure (theta-related)
        cross_gamma: Cross-gamma friction term
        volatility_drag: VIX-based volatility drag coefficient
        regime: Current market regime classification
        energy: Movement energy (cost to move price)
        confidence: Hedge Engine's confidence in its outputs
        realized_move_score: Realized vs predicted move alignment
        cross_asset_pressure: Correlation-weighted cross-asset pressure
    """
    net_pressure: float
    pressure_mtf: Dict[str, float] = Field(default_factory=dict)
    gamma_curvature: float
    vanna_drift: float
    charm_decay: float
    cross_gamma: float
    volatility_drag: float
    regime: str
    energy: float
    confidence: float
    realized_move_score: float
    cross_asset_pressure: float


class HedgeAgentOutput(BaseModel):
    """
    Output schema for Hedge Agent interpretation.
    
    Clean, typed signal for consumption by the Composer Agent.
    
    Attributes:
        direction: Qualitative direction classification
        strength: Field strength [0-1] - how hard to move price
        confidence: Agent confidence [0-1] in interpretation
        regime: Regime classification passed through
        notes: List of interpretation notes/flags
    """
    direction: str = Field(
        description="Direction classification: strong bull, weak bull, neutral, weak bear, strong bear, chaotic"
    )
    strength: float = Field(
        ge=0.0,
        le=1.0,
        description="Field strength - energy cost to move price (0=easy, 1=hard)",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in interpretation",
    )
    regime: str = Field(
        description="Market regime: quadratic, cubic, double_well, jump, etc."
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Interpretation notes and flags",
    )
