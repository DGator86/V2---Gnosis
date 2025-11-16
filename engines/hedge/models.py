from __future__ import annotations

"""Pydantic models for Hedge Engine v3.0 internal data structures."""

from typing import Dict, Optional

import polars as pl
from pydantic import BaseModel, Field


class GreekInputs(BaseModel):
    """Raw Greek data extracted from options chain."""

    class Config:
        arbitrary_types_allowed = True

    chain: pl.DataFrame
    spot: float
    vix: Optional[float] = None
    vol_of_vol: float = 0.0
    liquidity_lambda: float = 0.0
    timestamp: float


class DealerSignOutput(BaseModel):
    """Dealer positioning sign estimation."""

    net_dealer_gamma: float
    net_dealer_vanna: float
    net_dealer_charm: float
    dealer_sign: float = Field(ge=-1.0, le=1.0, description="Net dealer positioning: -1=short, +1=long")
    confidence: float = Field(ge=0.0, le=1.0)
    oi_weighted_strike_center: float
    metadata: Dict[str, float] = Field(default_factory=dict)


class GammaFieldOutput(BaseModel):
    """Gamma pressure field calculation."""

    gamma_exposure: float
    gamma_pressure_up: float
    gamma_pressure_down: float
    gamma_regime: str
    dealer_gamma_sign: float
    strike_weighted_gamma: Dict[float, float]
    pin_zones: list[tuple[float, float]] = Field(default_factory=list)
    metadata: Dict[str, float] = Field(default_factory=dict)


class VannaFieldOutput(BaseModel):
    """Vanna pressure field calculation."""

    vanna_exposure: float
    vanna_pressure_up: float
    vanna_pressure_down: float
    vanna_regime: str
    vol_sensitivity: float
    vanna_shock_absorber: float
    metadata: Dict[str, float] = Field(default_factory=dict)


class CharmFieldOutput(BaseModel):
    """Charm decay field calculation."""

    charm_exposure: float
    charm_drift_rate: float
    time_decay_pressure: float
    charm_regime: str
    decay_acceleration: float
    metadata: Dict[str, float] = Field(default_factory=dict)


class ElasticityOutput(BaseModel):
    """Elasticity calculation from Greek fields."""

    elasticity: float = Field(gt=0.0, description="Market stiffness/resistance to movement")
    elasticity_up: float
    elasticity_down: float
    asymmetry_ratio: float
    gamma_component: float
    vanna_component: float
    charm_component: float
    liquidity_friction: float
    oi_density_modifier: float
    metadata: Dict[str, float] = Field(default_factory=dict)


class MovementEnergyOutput(BaseModel):
    """Movement energy required to push price through elasticity."""

    movement_energy_up: float
    movement_energy_down: float
    net_energy: float
    energy_asymmetry: float
    barrier_strength: float
    acceleration_likelihood: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, float] = Field(default_factory=dict)


class RegimeOutput(BaseModel):
    """Multi-dimensional regime classification."""

    primary_regime: str
    gamma_regime: str
    vanna_regime: str
    charm_regime: str
    jump_risk_regime: str
    volatility_regime: str
    potential_shape: str
    regime_confidence: float = Field(ge=0.0, le=1.0)
    regime_stability: float = Field(ge=0.0, le=1.0)
    cross_asset_correlation: float = Field(ge=-1.0, le=1.0)
    metadata: Dict[str, float] = Field(default_factory=dict)


class MTFFusionOutput(BaseModel):
    """Multi-timeframe fusion result."""

    fused_pressure_up: float
    fused_pressure_down: float
    fused_net_pressure: float
    fused_elasticity: float
    fused_energy: float
    timeframe_weights: Dict[str, float]
    realized_move_score: float
    adaptive_confidence: float = Field(ge=0.0, le=1.0)
    volatility_penalty: float
    metadata: Dict[str, float] = Field(default_factory=dict)


class HedgeEngineOutput(BaseModel):
    """Complete hedge engine output with all components."""

    # Primary outputs
    pressure_up: float
    pressure_down: float
    net_pressure: float
    elasticity: float
    movement_energy: float
    
    # Detailed breakdowns
    elasticity_up: float
    elasticity_down: float
    movement_energy_up: float
    movement_energy_down: float
    energy_asymmetry: float
    
    # Greek components
    gamma_pressure: float
    vanna_pressure: float
    charm_pressure: float
    dealer_gamma_sign: float
    
    # Regime classification
    primary_regime: str
    gamma_regime: str
    vanna_regime: str
    charm_regime: str
    jump_risk_regime: str
    potential_shape: str
    
    # Confidence and quality
    confidence: float = Field(ge=0.0, le=1.0)
    regime_stability: float = Field(ge=0.0, le=1.0)
    
    # Cross-asset and MTF
    cross_asset_correlation: float = Field(ge=-1.0, le=1.0)
    mtf_weights: Dict[str, float] = Field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, float] = Field(default_factory=dict)
