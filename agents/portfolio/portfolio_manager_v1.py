# agents/portfolio/portfolio_manager_v1.py

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List

from agents.trade_agent.schemas import TradeIdea

from .risk_limits import PortfolioRiskLimits
from .schemas import OrderAction, OrderInstruction, PortfolioState


class PortfolioManagerV1:
    """
    Stateless Portfolio Manager.

    Input:
      - PortfolioState snapshot
      - Ranked TradeIdeas (sized, scored)
      - PortfolioRiskLimits

    Output:
      - List[OrderInstruction] describing which new trades to OPEN (v1).

    This does NOT track PnL or update state. That is the caller's job.
    """

    def __init__(self, risk_limits: PortfolioRiskLimits):
        self._limits = risk_limits

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_execution_plan(
        self,
        portfolio: PortfolioState,
        ideas: Iterable[TradeIdea],
    ) -> List[OrderInstruction]:
        """
        Build an execution plan for opening new positions.

        - Respects global risk, per-asset risk, per-strategy risk, and max positions.
        - Consumes ideas in descending ranking_score order.
        """
        ideas = sorted(
            [i for i in ideas if (i.ranking_score or 0.0) > 0.0],
            key=lambda x: (x.ranking_score or 0.0),
            reverse=True,
        )

        plan: List[OrderInstruction] = []

        # Compute current risk usage
        equity = portfolio.equity
        if equity <= 0.0:
            return plan  # no capital, no trades

        current_portfolio_risk = self._estimate_current_portfolio_risk(portfolio, equity)
        current_positions = len(portfolio.positions)

        risk_by_asset = self._aggregate_risk_by_asset(portfolio, equity)
        risk_by_strategy = self._aggregate_risk_by_strategy(portfolio, equity)

        for idea in ideas:
            if current_positions >= self._limits.max_open_positions:
                break

            max_risk = idea.max_risk or 0.0
            if max_risk <= 0.0:
                continue

            new_risk_fraction = max_risk / equity

            # Global caps
            if (
                current_portfolio_risk + new_risk_fraction
                > self._limits.max_portfolio_risk
            ):
                continue

            if new_risk_fraction > self._limits.max_risk_per_trade:
                # Hard cap per trade
                continue

            # Per-asset cap
            asset_risk = risk_by_asset[idea.asset] + new_risk_fraction
            if asset_risk > self._limits.max_risk_per_asset:
                continue

            # Per-strategy cap
            strat_cap = self._limits.strategy_cap(idea.strategy_type)
            strategy_risk = risk_by_strategy[idea.strategy_type] + new_risk_fraction
            if strategy_risk > strat_cap:
                continue

            # Passed all constraints: include in plan
            order = OrderInstruction(
                action=OrderAction.OPEN,
                asset=idea.asset,
                strategy_type=idea.strategy_type,
                size_delta=idea.recommended_size or 1,
                notional_risk=max_risk,
                reason=self._build_reason_string(idea),
                source_idea=idea,
            )
            plan.append(order)

            # Update accounting for subsequent ideas
            current_portfolio_risk += new_risk_fraction
            risk_by_asset[idea.asset] = asset_risk
            risk_by_strategy[idea.strategy_type] = strategy_risk
            current_positions += 1

        return plan

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_current_portfolio_risk(
        portfolio: PortfolioState,
        equity: float,
    ) -> float:
        """
        Approximate total capital at risk as sum(max_risk_allocated) / equity.
        """
        total_risk = sum(p.max_risk_allocated for p in portfolio.positions)
        return min(1.0, total_risk / equity) if equity > 0.0 else 0.0

    @staticmethod
    def _aggregate_risk_by_asset(
        portfolio: PortfolioState,
        equity: float,
    ) -> dict[str, float]:
        risk_by_asset: dict[str, float] = defaultdict(float)
        for p in portfolio.positions:
            risk_by_asset[p.asset] += p.max_risk_allocated / equity
        return risk_by_asset

    @staticmethod
    def _aggregate_risk_by_strategy(
        portfolio: PortfolioState,
        equity: float,
    ) -> dict:
        risk_by_strategy: dict = defaultdict(float)
        for p in portfolio.positions:
            risk_by_strategy[p.strategy_type] += p.max_risk_allocated / equity
        return risk_by_strategy

    @staticmethod
    def _build_reason_string(idea: TradeIdea) -> str:
        parts = [
            f"ranking_score={idea.ranking_score:.3f}"
            if idea.ranking_score is not None
            else None,
            f"confidence={idea.confidence:.2f}",
            f"strategy={idea.strategy_type.value}",
        ]
        return " | ".join(p for p in parts if p)
