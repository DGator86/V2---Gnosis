"""Typed configuration models for Super Gnosis."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuntimeConfig(BaseModel):
    """Runtime behaviour toggles."""

    log_level: str = "INFO"
    checkpoints_dir: str = "logs/checkpoints"
    enable_checkpointing: bool = True
    max_checkpoint_age_hours: int = 24

    model_config = ConfigDict(extra="allow")


class HedgeConfig(BaseModel):
    """Configuration for the hedge engine."""

    gamma_squeeze_threshold: float = 1e6
    vanna_flow_threshold: float = 5e5
    pin_threshold: float = 5e4
    max_chain_size: int = 5000

    model_config = ConfigDict(extra="allow")


class LiquidityConfig(BaseModel):
    """Configuration for the liquidity engine."""

    lookback: int = 30
    intraday_minutes: int = 60
    thin_threshold: float = 0.001
    high_threshold: float = 0.0001
    one_sided_threshold: float = 0.6

    model_config = ConfigDict(extra="allow")


class SentimentConfig(BaseModel):
    """Configuration for the sentiment engine."""

    bullish_threshold: float = 0.3
    bearish_threshold: float = 0.3
    lookback_hours: int = 24

    model_config = ConfigDict(extra="allow")


class ElasticityConfig(BaseModel):
    """Configuration for the elasticity engine."""

    lookback: int = 30
    baseline_move_cost: float = 1.0

    model_config = ConfigDict(extra="allow")


class EnginesConfig(BaseModel):
    """Container for all engine configurations."""

    hedge: HedgeConfig = Field(default_factory=HedgeConfig)
    liquidity: LiquidityConfig = Field(default_factory=LiquidityConfig)
    sentiment: SentimentConfig = Field(default_factory=SentimentConfig)
    elasticity: ElasticityConfig = Field(default_factory=ElasticityConfig)

    model_config = ConfigDict(extra="allow")


class LookaheadConfig(BaseModel):
    """Configuration for lookahead modelling."""

    horizons: List[int] = Field(default_factory=lambda: [1, 5, 20])
    scenarios: List[str] = Field(default_factory=lambda: ["base", "stress", "euphoria"])
    monte_carlo_sims: int = 500

    model_config = ConfigDict(extra="allow")


class TrackingConfig(BaseModel):
    """Ledger and tracking configuration."""

    ledger_path: str = "data/ledger.jsonl"

    model_config = ConfigDict(extra="allow")


class FeedbackConfig(BaseModel):
    """Feedback engine configuration."""

    reward_metric: str = "sharpe"
    learning_rate: float = 0.2
    window_size: int = 100

    model_config = ConfigDict(extra="allow")


class SecurityConfig(BaseModel):
    """Security related configuration."""

    enable_guardrails: bool = True

    model_config = ConfigDict(extra="allow")


class MemoryConfig(BaseModel):
    """Memory subsystem configuration."""

    short_term_max_items: int = 100
    long_term_max_items: int = 1000

    model_config = ConfigDict(extra="allow")


class PrimaryAgentConfig(BaseModel):
    """Base configuration for primary agents."""

    enabled: bool = True
    confidence_threshold: float = 0.5

    model_config = ConfigDict(extra="allow")


class ComposerAgentConfig(PrimaryAgentConfig):
    """Composer specific configuration."""

    voting_method: str = "weighted_confidence"
    min_agreement_score: float = 0.6
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "primary_hedge": 1.0,
        "primary_liquidity": 1.0,
        "primary_sentiment": 1.0,
    })


class TradeAgentConfig(BaseModel):
    """Trade agent configuration."""

    min_confidence: float = 0.5
    max_capital_per_trade: float = 10000.0
    risk_per_unit: float = 500.0
    max_legs: int = 4

    model_config = ConfigDict(extra="allow")


class AgentsConfig(BaseModel):
    """Container for agent configurations."""

    hedge: PrimaryAgentConfig = Field(default_factory=PrimaryAgentConfig)
    liquidity: PrimaryAgentConfig = Field(default_factory=PrimaryAgentConfig)
    sentiment: PrimaryAgentConfig = Field(default_factory=PrimaryAgentConfig)
    composer: ComposerAgentConfig = Field(default_factory=ComposerAgentConfig)
    trade: TradeAgentConfig = Field(default_factory=TradeAgentConfig)

    model_config = ConfigDict(extra="allow")


class ExecutionConfig(BaseModel):
    """Execution and broker configuration."""

    broker: str = "alpaca_paper"  # Options: alpaca_paper, alpaca_live, simulated
    mode: str = "paper"  # Options: paper, live
    risk_per_trade_pct: float = 1.0
    max_position_size_pct: float = 2.0
    max_daily_loss_usd: float = 5000.0
    loop_interval_seconds: int = 60
    enable_trading: bool = True

    model_config = ConfigDict(extra="allow")


class AdaptersConfig(BaseModel):
    """Adapter configuration stub allowing arbitrary keys."""

    model_config = ConfigDict(extra="allow")


class AppConfig(BaseModel):
    """Root application configuration."""

    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    engines: EnginesConfig = Field(default_factory=EnginesConfig)
    lookahead: LookaheadConfig = Field(default_factory=LookaheadConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    adapters: AdaptersConfig = Field(default_factory=AdaptersConfig)

    model_config = ConfigDict(extra="allow")

    def get(self, path: str, default: Optional[object] = None) -> Optional[object]:
        """Dictionary-style lookup helper for legacy callers."""

        current: object = self.model_dump()
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
