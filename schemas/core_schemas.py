"""
Core schemas for DHPE pipeline
Defines all data structures used across engines and agents
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

from pydantic import BaseModel, Field
import json
import uuid


@dataclass
class RawInputs:
    """Raw market data inputs"""
    symbol: str
    timestamp: float
    options: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    news: List[Dict[str, Any]]
    orderbook: Optional[Dict[str, Any]] = None
    fundamentals: Optional[Dict[str, Any]] = None


@dataclass
class EngineOutput:
    """Standardized output from any engine"""
    kind: Literal["hedge", "volume", "sentiment"]
    features: Dict[str, float]
    metadata: Dict[str, Any]
    timestamp: float
    confidence: float = 1.0


@dataclass
class StandardSnapshot:
    """Unified snapshot consumed by all primary agents"""
    timestamp: float
    symbol: str
    hedge: Dict[str, float]
    volume: Dict[str, float]
    sentiment: Dict[str, float]
    regime: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Forecast:
    """Look-ahead forecast from any horizon"""
    horizon: int  # bars/minutes
    exp_return: float
    risk: float
    prob_win: float
    scenarios: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Suggestion:
    """Suggestion emitted by primary agents or composer"""
    id: str
    layer: Literal["primary_hedge", "primary_volume", "primary_sentiment", "composer"]
    symbol: str
    action: str  # 'long', 'short', 'hold', 'spread:call_debit', etc.
    params: Dict[str, Any]
    confidence: float
    forecast: Forecast
    timestamp: float
    reasoning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['forecast'] = asdict(self.forecast)
        return d
    
    @staticmethod
    def create(layer: str, symbol: str, action: str, params: Dict[str, Any],
               confidence: float, forecast: Forecast, reasoning: str = None) -> 'Suggestion':
        return Suggestion(
            id=str(uuid.uuid4())[:8],
            layer=layer,
            symbol=symbol,
            action=action,
            params=params,
            confidence=confidence,
            forecast=forecast,
            timestamp=datetime.now().timestamp(),
            reasoning=reasoning
        )


@dataclass
class Position:
    """Opened position (linked to suggestion)"""
    id: str  # matches suggestion id
    symbol: str
    side: Literal["long", "short", "flat"]
    size: float
    entry_price: float
    entry_time: float
    strategy_type: str  # 'directional', 'spread', 'hedge'
    legs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Result:
    """Result of a closed position (linked to suggestion)"""
    id: str  # matches suggestion id
    exit_price: float
    exit_time: float
    pnl: float
    pnl_pct: float
    realized_horizon: int
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolEvent:
    """Event from a tool call (for A2A comms)"""
    tool: str
    success: bool
    latency_ms: int
    output: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class A2AMessage:
    """Agent-to-Agent communication message"""
    source_agent: str
    intent: str
    version: str
    payload: Dict[str, Any]
    tools: List[ToolEvent] = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'A2AMessage':
        d = json.loads(data)
        d['tools'] = [ToolEvent(**t) for t in d.get('tools', [])]
        return A2AMessage(**d)


@dataclass
class MemoryItem:
    """Single memory item with decay"""
    content: str
    embedding: Optional[List[float]]
    timestamp: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def age_days(self, now: float = None) -> float:
        if now is None:
            now = datetime.now().timestamp()
        return (now - self.timestamp) / 86400.0


@dataclass
class Checkpoint:
    """Orchestration checkpoint for resumable runs"""
    run_id: str
    agent_name: str
    step: int
    state: Dict[str, Any]
    timestamp: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data: str) -> 'Checkpoint':
        return Checkpoint(**json.loads(data))


class TechnicalFeatures(BaseModel):
    """Standardized technical indicator features shared across engines."""

    rsi: Optional[float] = Field(
        default=None,
        description=(
            "Written by the technical feature extractor; read primarily by the "
            "Sentiment Engine/Agent to detect overbought and oversold pressure."
        ),
    )
    stoch_rsi: Optional[float] = Field(
        default=None,
        description=(
            "Produced for the Sentiment Engine to judge exhaustion and reversals; "
            "also referenced by the Composer when classifying squeeze vs. chop."
        ),
    )
    macd: Optional[float] = Field(
        default=None,
        description="Sentiment Engine input summarised for the Sentiment Agent trend bias.",
    )
    macd_signal: Optional[float] = Field(
        default=None,
        description="Sentiment Engine input enabling cross-over strength evaluation.",
    )
    adx: Optional[float] = Field(
        default=None,
        description="Sentiment Engine and Composer read to gauge trend strength regimes.",
    )
    supertrend_distance: Optional[float] = Field(
        default=None,
        description="Sentiment Agent consumes to determine crowd leaning and stop proximity.",
    )
    bollinger_bandwidth: Optional[float] = Field(
        default=None,
        description="Generated for Sentiment (compression) and Liquidity (range state) engines.",
    )
    keltner_compression: Optional[float] = Field(
        default=None,
        description="Liquidity Engine reads for expansion risk; Sentiment Agent flags squeeze setups.",
    )
    atr: Optional[float] = Field(
        default=None,
        description="Liquidity Engine baseline for expected bar size passed to Liquidity Agent.",
    )
    volatility_percentile: Optional[float] = Field(
        default=None,
        description="Hedge Engine compares realised vs implied; Composer moderates regime multipliers.",
    )
    obv: Optional[float] = Field(
        default=None,
        description="Sentiment Engine interprets participation vs. price for accumulation signals.",
    )
    mfi: Optional[float] = Field(
        default=None,
        description="Sentiment Agent reads for crowd conviction and potential blow-off conditions.",
    )
    crowding_score: Optional[float] = Field(
        default=None,
        description="Composer and Trade Agent consume aggregated indicator skew from Sentiment Engine.",
    )


class OrderFlowFeatures(BaseModel):
    """Order-flow derived features anchored in the Liquidity Engine."""

    net_aggressive_volume: Optional[float] = Field(
        default=None,
        description="Liquidity Engine writes from tape analysis; Liquidity Agent summarises pressure.",
    )
    bid_ask_imbalance: Optional[float] = Field(
        default=None,
        description="Generated by Liquidity Engine L2 parser; Sentiment Agent uses for conviction.",
    )
    liquidity_gap_score: Optional[float] = Field(
        default=None,
        description="Liquidity Engine flags fragile zones; Composer maps into path risk.",
    )
    absorption_score: Optional[float] = Field(
        default=None,
        description="Liquidity Agent emits for hold/flip probability after analysing resting orders.",
    )
    stop_run_intensity: Optional[float] = Field(
        default=None,
        description="Liquidity Engine identifies liquidity grabs; Sentiment Agent reads emotional surge.",
    )
    sweep_frequency: Optional[float] = Field(
        default=None,
        description="Liquidity Engine tape models detect sweeps; Composer weighs breakout odds.",
    )
    iceberg_detection: Optional[float] = Field(
        default=None,
        description="Liquidity Agent exposes hidden size inference back to Composer and Trade Agent.",
    )
    block_trade_ratio: Optional[float] = Field(
        default=None,
        description="Liquidity Engine tallies block prints; Sentiment Engine infers smart-money flow.",
    )
    delta_price_volume_divergence: Optional[float] = Field(
        default=None,
        description="Sentiment Engine reinterprets to decide if flow is effective or absorbed.",
    )


class ElasticityMetrics(BaseModel):
    """Elasticity primitives produced before Composer fusion."""

    microstructure_elasticity: Optional[float] = Field(
        default=None,
        description=(
            "Liquidity Engine output (dP/dQ) that the Liquidity Agent reports upstream."
        ),
    )
    dealer_elasticity: Optional[float] = Field(
        default=None,
        description=(
            "Hedge Engine computes ΔQ/ΔP hedge demand; Hedge Agent relays squeeze risk."
        ),
    )
    sentiment_pressure_multiplier: Optional[float] = Field(
        default=None,
        description=(
            "Sentiment Engine derived willingness-to-push factor; Composer scales energy needs."
        ),
    )
    volatility_adjusted_impact: Optional[float] = Field(
        default=None,
        description=(
            "Liquidity Engine blends ATR/vol with impact curve; Composer uses for path breadth."
        ),
    )


class ReturnDistribution(BaseModel):
    """Short-horizon return shape predicted by ML models."""

    mean: float = Field(
        ..., description="Composer meta-ML writes expectation; Trade Agent consumes for targeting."
    )
    variance: float = Field(
        ..., description="Composer meta-ML writes dispersion; Adaptation layer uses for calibration."
    )
    skewness: float = Field(
        ..., description="Composer and Trade Agent use to size asymmetric pay-offs."
    )


class MLPredictionPacket(BaseModel):
    """Envelope for any ML model output across engines and Composer."""

    model_name: str = Field(..., description="Name of the ML component producing this packet.")
    source: Literal[
        "hedge_engine",
        "liquidity_engine",
        "sentiment_engine",
        "composer",
        "adaptation_layer",
    ] = Field(
        ..., description="Identifies which engine or layer wrote the prediction for routing."
    )
    symbol: str = Field(..., description="Target instrument for the prediction.")
    horizon: int = Field(
        ..., description="Forward horizon in minutes/bars shared with Composer and Trade Agent."
    )
    scenario_probabilities: Dict[str, float] = Field(
        default_factory=dict,
        description="Composer meta-model reads to classify regime; Agents inspect for alignment.",
    )
    return_distribution: Optional[ReturnDistribution] = Field(
        default=None,
        description="Provided by Composer meta-ML; Trade Agent and Adaptation layer consume directly.",
    )
    path_shape: Optional[Literal["straight", "grind", "whipsaw", "parabolic"]] = Field(
        default=None,
        description="Composer model writes predicted path; Trade Agent maps to strategy templates.",
    )
    feature_overrides: Dict[str, float] = Field(
        default_factory=dict,
        description="Adaptation layer can feed adjustments back into engines for recalibration.",
    )
    generated_at: float = Field(
        default_factory=lambda: datetime.now().timestamp(),
        description="Timestamp for downstream sequencing.",
    )


class MarketScenarioPacket(BaseModel):
    """Composer-fused scenario with elasticity and energy metrics for Trade Agent."""

    scenario: Literal["trend", "squeeze", "fakeout", "chop"] = Field(
        ..., description="Composer Agent writes canonical scenario consumed by Trade Agent."
    )
    scenario_confidence: float = Field(
        ..., description="Confidence score forwarded to Trade Agent risk selection.",
    )
    scenario_probabilities: Dict[str, float] = Field(
        default_factory=dict,
        description="Full distribution made visible to Adaptation layer for recalibration.",
    )
    net_elasticity: float = Field(
        ..., description="Composer fusion of Liquidity and Hedge elasticities for all agents.",
    )
    energy_to_move: float = Field(
        ..., description="Energy metric shared with Trade Agent for target feasibility decisions.",
    )
    expected_path_shape: Literal["straight", "grind", "whipsaw", "parabolic"] = Field(
        ..., description="Direct input to Trade Agent playbook selection.",
    )
    horizon: int = Field(
        ..., description="Prediction horizon aligning with MLPredictionPacket outputs."
    )
    return_distribution: ReturnDistribution = Field(
        ..., description="Composer-provided distribution reused by Adaptation layer for scoring.",
    )
    contributing_features: Dict[str, float] = Field(
        default_factory=dict,
        description="Key driver summary exposed to all agents for explainability and audits.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form annotations shared across Composer, Adaptation, and Trade layers.",
    )
