from __future__ import annotations

"""Pydantic models for Liquidity Engine v1.0 internal data structures."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# STRUCTURAL COMPONENTS
# ============================================================


class LiquidityZone(BaseModel):
    """Represents a price zone with specific liquidity behavior."""

    price_start: float = Field(..., description="Lower bound of the zone")
    price_end: float = Field(..., description="Upper bound of the zone")
    strength: float = Field(..., ge=0.0, le=1.0, description="Zone strength [0-1]")
    zone_type: Literal["absorption", "displacement"] = Field(..., description="Zone behavior type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    volume_density: float = Field(default=0.0, ge=0.0, description="Volume concentration in zone")


class LiquidityGap(BaseModel):
    """Represents a liquidity void or gap."""

    price_start: float = Field(..., description="Lower bound of gap")
    price_end: float = Field(..., description="Upper bound of gap")
    severity: float = Field(..., ge=0.0, le=1.0, description="Gap severity [0-1]")
    expected_velocity: float = Field(default=1.0, ge=0.0, description="Expected price velocity through gap")


class ProfileNode(BaseModel):
    """Volume profile node (HVN/LVN)."""

    price: float = Field(..., description="Price level")
    volume: float = Field(..., ge=0.0, description="Volume at level")
    node_type: Literal["HVN", "LVN", "POC", "neutral"] = Field(..., description="Node classification")
    significance: float = Field(..., ge=0.0, le=1.0, description="Node importance [0-1]")
    support_resistance_strength: float = Field(default=0.0, ge=0.0, le=1.0)


# ============================================================
# PROCESSOR RESULTS
# ============================================================


class ProcessorResult(BaseModel):
    """Base class for all processor results."""

    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Processor confidence")
    metadata: Dict[str, float] = Field(default_factory=dict, description="Additional metrics")


class VolumeProcessorResult(ProcessorResult):
    """Volume analysis outputs."""

    volume_strength: float = Field(..., ge=0.0, le=1.0, description="Normalized volume support")
    buying_effort: float = Field(..., ge=0.0, le=1.0, description="Relative buying effort")
    selling_effort: float = Field(..., ge=0.0, le=1.0, description="Relative selling effort")
    exhaustion_flag: bool = Field(default=False, description="Volume exhaustion detected")
    rvol: float = Field(default=1.0, ge=0.0, description="Relative volume vs baseline")
    volume_trend: float = Field(default=0.0, ge=-1.0, le=1.0, description="Volume trend direction")


class OrderFlowProcessorResult(ProcessorResult):
    """Order flow analysis outputs."""

    ofi: float = Field(..., ge=-1.0, le=1.0, description="Order flow imbalance")
    sweep_flag: bool = Field(default=False, description="Aggressive sweep detected")
    iceberg_flag: bool = Field(default=False, description="Iceberg behavior detected")
    liquidity_taker_intensity: float = Field(..., ge=0.0, le=1.0, description="Taker aggression")
    bid_ask_imbalance: float = Field(default=0.0, ge=-1.0, le=1.0, description="Bid/ask time imbalance")


class MicrostructureProcessorResult(ProcessorResult):
    """Microstructure analysis outputs."""

    spread_cost: float = Field(..., ge=0.0, description="Spread cost per unit")
    microprice_direction: float = Field(..., ge=-1.0, le=1.0, description="Microprice bias")
    impact_slope: float = Field(..., ge=0.0, description="Local impact slope")
    quote_depth_ratio: float = Field(default=1.0, ge=0.0, description="Depth asymmetry")


class ImpactProcessorResult(ProcessorResult):
    """Market impact analysis outputs."""

    slippage_per_1pct_move: float = Field(..., ge=0.0, description="Expected slippage for 1% move")
    lambda_kyle: float = Field(..., ge=0.0, description="Kyle's lambda coefficient")
    amihud: float = Field(..., ge=0.0, description="Amihud illiquidity metric")
    impact_energy: float = Field(..., ge=0.0, description="Energy-like impact measure")
    price_impact_asymmetry: float = Field(default=1.0, ge=0.0, description="Up/down impact ratio")


class DarkPoolProcessorResult(ProcessorResult):
    """Dark pool analysis outputs."""

    dp_accumulation: float = Field(..., ge=0.0, le=1.0, description="Accumulation strength")
    dp_distribution: float = Field(..., ge=0.0, le=1.0, description="Distribution strength")
    off_exchange_ratio: float = Field(..., ge=0.0, le=1.0, description="Off-exchange volume fraction")
    hidden_buying_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    hidden_selling_pressure: float = Field(default=0.0, ge=0.0, le=1.0)


class StructureProcessorResult(ProcessorResult):
    """Structural liquidity analysis outputs."""

    absorption_zones: List[LiquidityZone] = Field(default_factory=list)
    displacement_zones: List[LiquidityZone] = Field(default_factory=list)
    voids: List[LiquidityGap] = Field(default_factory=list)
    profile_nodes: List[ProfileNode] = Field(default_factory=list)
    poc_price: Optional[float] = Field(default=None, description="Point of Control price")
    value_area_high: Optional[float] = Field(default=None)
    value_area_low: Optional[float] = Field(default=None)


class WyckoffLiquidityProcessorResult(ProcessorResult):
    """Wyckoff liquidity analysis outputs."""

    wyckoff_phase: Literal["A", "B", "C", "D", "E", "Unknown"] = Field(default="Unknown")
    wyckoff_energy: float = Field(..., ge=0.0, le=1.0, description="Accumulation/distribution energy")
    absorption_vs_displacement_bias: float = Field(..., ge=-1.0, le=1.0, description="Net bias")
    spring_detected: bool = Field(default=False, description="Spring/upthrust detected")
    sos_detected: bool = Field(default=False, description="Sign of Strength detected")
    sow_detected: bool = Field(default=False, description="Sign of Weakness detected")


class VolatilityLiquidityProcessorResult(ProcessorResult):
    """Volatility-liquidity interaction outputs."""

    compression_energy: float = Field(..., ge=0.0, description="Stored compression energy")
    expansion_energy: float = Field(..., ge=0.0, description="Expansion potential")
    squeeze_flag: bool = Field(default=False, description="Volatility squeeze active")
    breakout_energy_required: float = Field(default=0.0, ge=0.0, description="Energy needed for breakout")
    compression_duration: int = Field(default=0, ge=0, description="Bars in compression")


# ============================================================
# LIQUIDITY ENGINE OUTPUT
# ============================================================


class LiquidityEngineOutput(BaseModel):
    """Complete liquidity engine output."""

    # Core liquidity metrics
    liquidity_score: float = Field(..., ge=0.0, le=1.0, description="Composite liquidity [0-1]")
    friction_cost: float = Field(..., ge=0.0, description="Expected friction per 1% move")
    
    # Impact metrics
    kyle_lambda: float = Field(..., ge=0.0, description="Kyle's lambda")
    amihud: float = Field(..., ge=0.0, description="Amihud illiquidity")
    
    # Structural features
    absorption_zones: List[LiquidityZone] = Field(default_factory=list)
    displacement_zones: List[LiquidityZone] = Field(default_factory=list)
    voids: List[LiquidityGap] = Field(default_factory=list)
    hvn_lvn_structure: List[ProfileNode] = Field(default_factory=list)
    
    # Order flow
    orderbook_imbalance: float = Field(..., ge=-1.0, le=1.0, description="Net OB imbalance")
    sweep_alerts: bool = Field(default=False)
    iceberg_alerts: bool = Field(default=False)
    
    # Volatility-liquidity
    compression_energy: float = Field(..., ge=0.0)
    expansion_energy: float = Field(..., ge=0.0)
    
    # Volume analysis
    volume_strength: float = Field(..., ge=0.0, le=1.0)
    buying_effort: float = Field(..., ge=0.0, le=1.0)
    selling_effort: float = Field(..., ge=0.0, le=1.0)
    
    # Dark pool
    off_exchange_ratio: float = Field(..., ge=0.0, le=1.0)
    hidden_accumulation: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Wyckoff
    wyckoff_phase: str = Field(default="Unknown")
    wyckoff_energy: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Regime
    liquidity_regime: Literal["Normal", "Thin", "Stressed", "Crisis", "Abundant"] = Field(
        ..., description="Liquidity regime classification"
    )
    regime_confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Path of Least Resistance
    polr_direction: float = Field(default=0.0, ge=-1.0, le=1.0, description="POLR vector")
    polr_strength: float = Field(default=0.0, ge=0.0, le=1.0, description="POLR conviction")
    
    # Meta
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall engine confidence")
    metadata: Dict[str, float] = Field(default_factory=dict)
