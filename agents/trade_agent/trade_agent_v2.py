# agents/trade_agent/trade_agent_v2.py

from __future__ import annotations

from typing import Iterable, List

from .greeks_matcher import annotate_with_greeks_context
from .ranking_engine import StrategyRankingEngine
from .risk_calculator import apply_risk_and_sizing
from .schemas import ComposerTradeContext, TradeIdea
from .stock_strategies import build_stock_trade_idea
from .strategy_selector import select_strategy_builders


class TradeAgentV2:
    """
    Stateless Trade Agent.
    - Input: ComposerTradeContext (adapter from CompositeMarketDirective)
    - Output: Ranked list of TradeIdea objects
    """

    def __init__(self, default_capital: float = 10_000.0):
        self._default_capital = float(default_capital)
        self._ranking_engine = StrategyRankingEngine()

    def generate_trade_ideas(
        self,
        ctx: ComposerTradeContext,
        underlying_price: float,
        capital: float | None = None,
    ) -> list[TradeIdea]:
        """
        Main entrypoint. Stateless.
        """
        cap = float(capital or self._default_capital)

        # 1) build stock idea
        ideas: list[TradeIdea] = [build_stock_trade_idea(ctx)]

        # 2) select and build option strategies
        builders = select_strategy_builders(ctx)
        for builder in builders:
            idea = builder(ctx, underlying_price)
            ideas.append(idea)

        # 3) annotate with Greeks / field context
        ideas = [annotate_with_greeks_context(idea, ctx) for idea in ideas]

        # 4) apply risk & sizing
        ideas = apply_risk_and_sizing(ideas, ctx, capital=cap)

        # 5) rank strategies (Phase 6: Strategy Ranking Engine v1.0)
        ideas = self._ranking_engine.rank(ideas, ctx, max_capital=cap)

        return ideas
