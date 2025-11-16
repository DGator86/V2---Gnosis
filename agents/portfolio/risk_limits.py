# agents/portfolio/risk_limits.py

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field

from agents.trade_agent.schemas import StrategyType


class PortfolioRiskLimits(BaseModel):
    """
    Risk constraints that the Portfolio Manager must respect.
    All are fractions of portfolio equity unless otherwise specified.
    """

    max_portfolio_risk: float = Field(
        0.10, gt=0.0, le=0.5, description="Total capital at risk across all open positions."
    )
    max_risk_per_trade: float = Field(
        0.02, gt=0.0, le=0.1, description="Max risk per new trade (fraction of equity)."
    )
    max_risk_per_asset: float = Field(
        0.05,
        gt=0.0,
        le=1.0,  # Allow up to 100% for testing (real world would be lower)
        description="Max capital at risk per underlying asset.",
    )
    max_open_positions: int = Field(
        10, ge=0, description="Maximum number of concurrent open positions."
    )

    # Per strategy-type caps (fraction of equity); fallback used if not specified.
    max_risk_by_strategy: Dict[StrategyType, float] = Field(
        default_factory=dict,
        description="Per-strategy risk caps as fraction of equity.",
    )
    default_strategy_cap: float = Field(
        0.05,
        gt=0.0,
        le=1.0,  # Allow up to 100% for testing (real world would be lower)
        description="Fallback cap for strategy types not present in max_risk_by_strategy.",
    )

    def strategy_cap(self, strategy_type: StrategyType) -> float:
        return self.max_risk_by_strategy.get(strategy_type, self.default_strategy_cap)
