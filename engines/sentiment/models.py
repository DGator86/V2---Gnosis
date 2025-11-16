"""Internal Pydantic models for Sentiment Engine v1.0."""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Base Signal Schema
# ============================================================================

class SentimentSignal(BaseModel):
    """
    Base signal output from any sentiment processor.
    
    Attributes:
        value: Normalized signal value in range [-1, 1] where:
               -1 = extreme bearish
                0 = neutral
               +1 = extreme bullish
        confidence: Signal confidence in range [0, 1]
        weight: Base weight for fusion (typically 1.0, adjusted in fusion)
        driver: Human-readable name identifying the signal source
    """
    value: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(gt=0.0, default=1.0)
    driver: str


# ============================================================================
# Wyckoff Processor Outputs
# ============================================================================

class WyckoffPhase(BaseModel):
    """Wyckoff accumulation/distribution phase detection."""
    phase: Literal["A", "B", "C", "D", "E", "Unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    description: str


class WyckoffSignals(BaseModel):
    """Complete output from Wyckoff processor."""
    phase: WyckoffPhase
    demand_supply_ratio: float  # >1 = demand dominant, <1 = supply dominant
    spring_detected: bool
    utad_detected: bool
    operator_bias: float = Field(ge=-1.0, le=1.0)  # Composite operator positioning
    strength_score: float = Field(ge=0.0, le=1.0)  # Overall Wyckoff strength


# ============================================================================
# Oscillator Processor Outputs
# ============================================================================

class RSISignals(BaseModel):
    """RSI-derived signals."""
    value: float = Field(ge=0.0, le=100.0)
    overbought: bool
    oversold: bool
    energy_decay_slope: float  # Rate of change in RSI
    divergence_detected: bool


class MFISignals(BaseModel):
    """Money Flow Index signals."""
    value: float = Field(ge=0.0, le=100.0)
    buy_pressure: float = Field(ge=0.0, le=1.0)
    sell_pressure: float = Field(ge=0.0, le=1.0)
    overbought: bool
    oversold: bool


class StochasticSignals(BaseModel):
    """Stochastic oscillator signals."""
    k_value: float = Field(ge=0.0, le=100.0)
    d_value: float = Field(ge=0.0, le=100.0)
    impulse: bool  # K crossing D upward
    reversion: bool  # K crossing D downward
    overbought: bool
    oversold: bool


class OscillatorSignals(BaseModel):
    """Combined oscillator processor output."""
    rsi: RSISignals
    mfi: MFISignals
    stochastic: StochasticSignals
    composite_score: float = Field(ge=-1.0, le=1.0)
    energy_decay: float  # Overall oscillator momentum decay


# ============================================================================
# Volatility Processor Outputs
# ============================================================================

class BollingerSignals(BaseModel):
    """Bollinger Band analysis."""
    percent_b: float  # Position within bands (0-1, can exceed)
    bandwidth: float  # Distance between bands (volatility measure)
    mean_reversion_pressure: float = Field(ge=-1.0, le=1.0)
    squeeze_active: bool


class KeltnerSignals(BaseModel):
    """Keltner Channel analysis."""
    position: float  # Position relative to channel
    expansion: bool
    compression: bool
    force_boundary: float  # Distance to boundary (elasticity measure)


class VolatilitySignals(BaseModel):
    """Combined volatility envelope processor output."""
    bollinger: BollingerSignals
    keltner: KeltnerSignals
    squeeze_detected: bool  # BB inside KC
    compression_energy: float = Field(ge=0.0)
    expansion_energy: float = Field(ge=0.0)
    envelope_score: float = Field(ge=-1.0, le=1.0)


# ============================================================================
# Flow/Bias Processor Outputs
# ============================================================================

class OrderFlowSignals(BaseModel):
    """Order flow imbalance analysis."""
    bid_ask_imbalance: float = Field(ge=-1.0, le=1.0)
    aggressive_buy_ratio: float = Field(ge=0.0, le=1.0)
    aggressive_sell_ratio: float = Field(ge=0.0, le=1.0)
    net_aggressor_pressure: float = Field(ge=-1.0, le=1.0)


class DarkPoolSignals(BaseModel):
    """Dark pool sentiment indicators."""
    dix_value: Optional[float] = None  # Dark Index (if available)
    gex_value: Optional[float] = None  # Gamma Exposure (if available)
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class FlowBiasSignals(BaseModel):
    """Combined flow/bias processor output."""
    order_flow: OrderFlowSignals
    dark_pool: DarkPoolSignals
    composite_flow_bias: float = Field(ge=-1.0, le=1.0)
    flow_confidence: float = Field(ge=0.0, le=1.0)


# ============================================================================
# Breadth/Regime Processor Outputs
# ============================================================================

class BreadthSignals(BaseModel):
    """Market breadth indicators."""
    advance_decline_ratio: float
    pct_above_ma: float = Field(ge=0.0, le=1.0)
    breadth_thrust: bool  # Strong directional move in breadth
    divergence_detected: bool


class RiskRegimeSignals(BaseModel):
    """Risk-on/risk-off regime detection."""
    regime: Literal["risk_on", "risk_off", "neutral"]
    rotation_score: float = Field(ge=-1.0, le=1.0)  # RRG-style rotation
    confidence: float = Field(ge=0.0, le=1.0)


class BreadthRegimeSignals(BaseModel):
    """Combined breadth/regime processor output."""
    breadth: BreadthSignals
    risk_regime: RiskRegimeSignals
    multi_period_regime: str  # Cross-timeframe regime consensus
    composite_score: float = Field(ge=-1.0, le=1.0)


# ============================================================================
# Energy Processor Outputs
# ============================================================================

class TrendEnergySignals(BaseModel):
    """Trend energy analysis."""
    momentum_energy: float = Field(ge=0.0)
    trend_coherence: float = Field(ge=0.0, le=1.0)  # Alignment across timeframes
    exhaustion_detected: bool
    buildup_detected: bool


class VolumeEnergySignals(BaseModel):
    """Volume-energy correlation."""
    volume_trend_correlation: float = Field(ge=-1.0, le=1.0)
    energy_per_volume: float  # Efficiency of energy expenditure
    volume_confirmation: bool


class MarketEnergySignals(BaseModel):
    """Combined market energy processor output."""
    trend_energy: TrendEnergySignals
    volume_energy: VolumeEnergySignals
    exhaustion_vs_continuation: float = Field(ge=-1.0, le=1.0)  # -1=exhausted, +1=building
    metabolic_load: float = Field(ge=0.0)  # Overall market energy expenditure


# ============================================================================
# Final Sentiment Envelope
# ============================================================================

class SentimentEnvelope(BaseModel):
    """
    Final output from Sentiment Engine v1.0.
    
    This is the canonical sentiment vector consumed by Agent 3 (Sentiment Agent)
    and ultimately the Composer Agent.
    """
    bias: Literal["bullish", "bearish", "neutral"]
    strength: float = Field(ge=0.0, le=1.0)  # Conviction strength
    energy: float = Field(ge=0.0)  # Market metabolic expenditure
    confidence: float = Field(ge=0.0, le=1.0)  # Meta-confidence of fusion
    drivers: Dict[str, float]  # Top contributing signals with their values
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Optional detailed breakdowns (for debugging/analysis)
    wyckoff_phase: Optional[str] = None
    liquidity_regime: Optional[str] = None
    volatility_regime: Optional[str] = None
    flow_regime: Optional[str] = None


# ============================================================================
# Processor Configuration Models
# ============================================================================

class ProcessorConfig(BaseModel):
    """Base configuration for processors."""
    enabled: bool = True
    weight: float = Field(gt=0.0, default=1.0)
    lookback_periods: int = Field(gt=0, default=20)


class WyckoffConfig(ProcessorConfig):
    """Wyckoff processor configuration."""
    phase_detection_sensitivity: float = Field(ge=0.0, le=1.0, default=0.7)
    spring_utad_threshold: float = Field(gt=0.0, default=0.02)


class OscillatorConfig(ProcessorConfig):
    """Oscillator processor configuration."""
    rsi_period: int = Field(gt=0, default=14)
    mfi_period: int = Field(gt=0, default=14)
    stoch_k_period: int = Field(gt=0, default=14)
    stoch_d_period: int = Field(gt=0, default=3)
    overbought_threshold: float = Field(ge=50.0, le=100.0, default=70.0)
    oversold_threshold: float = Field(ge=0.0, le=50.0, default=30.0)


class VolatilityConfig(ProcessorConfig):
    """Volatility processor configuration."""
    bb_period: int = Field(gt=0, default=20)
    bb_std_dev: float = Field(gt=0.0, default=2.0)
    kc_period: int = Field(gt=0, default=20)
    kc_atr_mult: float = Field(gt=0.0, default=2.0)


class FlowConfig(ProcessorConfig):
    """Flow/bias processor configuration."""
    orderflow_window: int = Field(gt=0, default=10)
    darkpool_enabled: bool = True


class BreadthConfig(ProcessorConfig):
    """Breadth/regime processor configuration."""
    ma_periods: List[int] = Field(default=[50, 200])
    regime_window: int = Field(gt=0, default=20)


class EnergyConfig(ProcessorConfig):
    """Energy processor configuration."""
    momentum_window: int = Field(gt=0, default=14)
    coherence_window: int = Field(gt=0, default=20)


class SentimentEngineConfig(BaseModel):
    """Master configuration for Sentiment Engine v1.0."""
    wyckoff: WyckoffConfig = Field(default_factory=WyckoffConfig)
    oscillators: OscillatorConfig = Field(default_factory=OscillatorConfig)
    volatility: VolatilityConfig = Field(default_factory=VolatilityConfig)
    flow: FlowConfig = Field(default_factory=FlowConfig)
    breadth: BreadthConfig = Field(default_factory=BreadthConfig)
    energy: EnergyConfig = Field(default_factory=EnergyConfig)
    
    # Fusion parameters
    bias_threshold: float = Field(ge=0.0, le=1.0, default=0.15)  # Threshold for neutral classification
    energy_scaling_factor: float = Field(gt=0.0, default=1.0)
    confidence_floor: float = Field(ge=0.0, le=1.0, default=0.1)
