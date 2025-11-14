"""Typed configuration models for the DHPE system."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuntimeConfig(BaseModel):
    log_level: str = "INFO"
    checkpoints_dir: str = "logs/checkpoints"
    enable_checkpointing: bool = True
    max_checkpoint_age_hours: int = 24

    model_config = ConfigDict(extra="allow")


class HedgeConfig(BaseModel):
    polars_threads: int = 4
    features: List[str] = Field(default_factory=lambda: [
        "gamma_pressure",
        "vanna_pressure",
        "charm_pressure",
    ])

    model_config = ConfigDict(extra="allow")


class VolumeConfig(BaseModel):
    window_bars: int = 20
    features: List[str] = Field(default_factory=lambda: [
        "flow_volume",
        "vwap",
        "trade_imbalance",
    ])

    model_config = ConfigDict(extra="allow")


class SentimentConfig(BaseModel):
    sources: List[str] = Field(default_factory=list)
    decay_half_life_days: float = 7.0
    min_confidence: float = 0.3
    max_memory_items: int = 5000

    model_config = ConfigDict(extra="allow")


class EnginesConfig(BaseModel):
    hedge: HedgeConfig = Field(default_factory=HedgeConfig)
    volume: VolumeConfig = Field(default_factory=VolumeConfig)
    sentiment: SentimentConfig = Field(default_factory=SentimentConfig)

    model_config = ConfigDict(extra="allow")


class LookaheadConfig(BaseModel):
    horizons: List[int] = Field(default_factory=lambda: [1, 5, 20, 60])
    scenarios: List[str] = Field(default_factory=lambda: ["base", "vol_up", "vol_down"])
    monte_carlo_sims: int = 1000
    confidence_levels: List[float] = Field(default_factory=lambda: [0.5, 0.75, 0.95])

    model_config = ConfigDict(extra="allow")


class TrackingConfig(BaseModel):
    ledger_path: str = "data/ledger.jsonl"
    enable_position_tracking: bool = True
    enable_result_tracking: bool = True
    backup_interval_minutes: int = 60

    model_config = ConfigDict(extra="allow")


class FeedbackConfig(BaseModel):
    reward_metric: str = "sharpe"
    learning_rate: float = 0.2
    window_size: int = 100
    enable_per_agent_learning: bool = True
    enable_regime_learning: bool = True

    model_config = ConfigDict(extra="allow")


class SecurityConfig(BaseModel):
    enable_guardrails: bool = True
    enable_pii_redaction: bool = True
    max_tool_timeout_seconds: int = 30
    allowed_tools: List[str] = Field(default_factory=list)
    blocked_patterns: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class MemoryConfig(BaseModel):
    short_term_max_items: int = 100
    long_term_max_items: int = 10000
    vector_dim: int = 768
    similarity_threshold: float = 0.7

    model_config = ConfigDict(extra="allow")


class PrimaryAgentConfig(BaseModel):
    enabled: bool = True
    confidence_threshold: float = 0.5
    rules: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class ComposerAgentConfig(PrimaryAgentConfig):
    voting_method: str = "weighted_confidence"
    min_agreement_score: float = 0.6
    strategy_mapping: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class AgentsConfig(BaseModel):
    primary_hedge: PrimaryAgentConfig = Field(default_factory=PrimaryAgentConfig)
    primary_volume: PrimaryAgentConfig = Field(default_factory=PrimaryAgentConfig)
    primary_sentiment: PrimaryAgentConfig = Field(default_factory=PrimaryAgentConfig)
    composer: ComposerAgentConfig = Field(default_factory=ComposerAgentConfig)

    model_config = ConfigDict(extra="allow")


class AdaptersConfig(BaseModel):
    model_config = ConfigDict(extra="allow")


class AppConfig(BaseModel):
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    engines: EnginesConfig = Field(default_factory=EnginesConfig)
    lookahead: LookaheadConfig = Field(default_factory=LookaheadConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    adapters: AdaptersConfig = Field(default_factory=AdaptersConfig)

    model_config = ConfigDict(extra="allow")

    def get(self, path: str, default: Optional[object] = None) -> Optional[object]:
        """Dictionary-style access for legacy callers."""
        current: object = self.model_dump()
        for key in path.split('.'):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
