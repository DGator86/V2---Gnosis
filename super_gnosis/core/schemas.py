from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field


class MarketTick(BaseModel):
    """Single bar / tick summary for the underlying."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None


class OptionsSnapshot(BaseModel):
    """Snapshot of options chain + Greeks at time t."""

    symbol: str
    timestamp: datetime
    # Minimal; extend with full slices later
    implied_vol: float
    total_open_interest: int
    total_volume: int
    gamma_exposure: float = Field(..., description="Dealer net gamma exposure")
    vanna_exposure: float
    charm_exposure: float


class TechnicalFeatures(BaseModel):
    """Technical indicator features computed for one bar."""

    rsi: float
    rsi_slope: float
    bollinger_bandwidth: float
    keltner_width: float
    atr: float
    obv: float
    mfi: float
    trend_strength: float  # e.g., ADX-like
    compression_score: float  # 0–1, Keltner/Bollinger squeeze-like


class OrderFlowFeatures(BaseModel):
    """Order-flow related features derived from tape / L2."""

    aggressive_buy_volume: float
    aggressive_sell_volume: float
    delta_volume: float
    order_imbalance: float
    avg_trade_size: float
    sweep_score: float
    absorption_score: float
    dark_pool_volume_estimate: Optional[float] = None


class ElasticityMetrics(BaseModel):
    """Microstructure + dealer elasticity and energy to move price."""

    dp_dq: float  # empirical price impact per volume
    dq_dp: float  # inverse elasticity
    dealer_dq_dp: float  # hedge demand per unit price
    net_elasticity: float  # fused measure (Composer-level)
    energy_per_pct_move: float  # approximate "effort" per 1% price move


class HedgeEngineSignals(BaseModel):
    """Hedge Engine interpretation at time t."""

    symbol: str
    timestamp: datetime
    directional_bias: Literal["up", "down", "neutral"]
    field_thrust: float  # magnitude of pressure
    field_stability: float  # 0–1; unstable → likely regime shift
    jump_risk_score: float  # tail risk probability proxy
    dealer_elasticity: float  # dealer-driven dq/dp
    confidence: float  # 0–1


class LiquidityEngineSignals(BaseModel):
    """Liquidity Engine interpretation at time t."""

    symbol: str
    timestamp: datetime
    liquidity_zones: Dict[str, float]  # e.g., {"support": 430.0, "resistance": 440.0}
    vacuum_score: float  # how empty the book is above/below
    breakout_probability: float
    mean_reversion_probability: float
    elasticity: float  # microstructure dq/dp based
    confidence: float


class SentimentEngineSignals(BaseModel):
    """Sentiment Engine interpretation at time t."""

    symbol: str
    timestamp: datetime
    trend_state: Literal["uptrend", "downtrend", "range", "unknown"]
    sentiment_bias: Literal["bullish", "bearish", "mixed", "apathetic"]
    trend_persistence_prob: float
    capitulation_prob: float
    accumulation_prob: float
    compression_prob: float  # squeeze likelihood
    confidence: float


class StandardizedSignals(BaseModel):
    """Unified, scaled signal packet output by Standardizer."""

    symbol: str
    timestamp: datetime
    # All scaled to, e.g., -1..1 or 0..1
    directional_score: float
    volatility_score: float
    liquidity_score: float
    sentiment_score: float
    energy_score: float
    jump_risk_score: float
    regime_label: Literal["trend", "range", "squeeze", "uncertain"]


class HedgeAgentPacket(BaseModel):
    symbol: str
    timestamp: datetime
    bias: Literal["up", "down", "neutral"]
    thrust_energy: float
    field_stability: float
    jump_risk_score: float
    confidence: float


class LiquidityAgentPacket(BaseModel):
    symbol: str
    timestamp: datetime
    range_low: float
    range_high: float
    vacuum_zones: List[float]
    breakout_bias: Literal["up", "down", "none"]
    energy_to_cross_range: float
    confidence: float


class SentimentAgentPacket(BaseModel):
    symbol: str
    timestamp: datetime
    trend_state: Literal["uptrend", "downtrend", "range", "unknown"]
    sentiment_bias: Literal["bullish", "bearish", "mixed", "apathetic"]
    compression_prob: float
    capitulation_prob: float
    trend_persistence_prob: float
    confidence: float


class MarketScenarioPacket(BaseModel):
    """Final fused view of the market state."""

    symbol: str
    timestamp: datetime
    scenario_label: Literal[
        "bull_trend",
        "bear_trend",
        "vol_squeeze_up",
        "vol_squeeze_down",
        "range_mean_revert",
        "chaotic_uncertain",
    ]
    expected_direction: Literal["up", "down", "flat"]
    expected_horizon_minutes: int
    net_elasticity: float
    energy_per_pct_move: float
    expected_return_pct: float
    expected_volatility_pct: float
    confidence: float


class TradeLeg(BaseModel):
    side: Literal["buy", "sell"]
    instrument_type: Literal["stock", "option"]
    symbol: str
    quantity: int
    option_type: Optional[Literal["call", "put"]] = None
    strike: Optional[float] = None
    expiry: Optional[datetime] = None


class TradeIdea(BaseModel):
    """Single trade idea generated by the Trade Agent."""

    symbol: str
    timestamp: datetime
    strategy_name: str
    scenario_label: str
    legs: List[TradeLeg]
    total_cost: float
    max_loss: float
    max_profit: Optional[float]
    target_price: float
    stop_price: float
    projected_profit_at_target: float
    probability_of_target: float
    recommended_risk_fraction: float  # e.g. Kelly or capped-Kelly fraction
