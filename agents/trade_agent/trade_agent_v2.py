# agents/trade_agent/trade_agent_v2.py

from __future__ import annotations

from typing import Iterable, List

from .exit_manager import create_default_exit_rules
from .greeks_matcher import annotate_with_greeks_context
from .ranking_engine import StrategyRankingEngine
from .risk_analyzer import enhance_idea_with_risk_metrics
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
        implied_vol: float = 0.30,
    ) -> list[TradeIdea]:
        """
        Main entrypoint. Stateless. Comprehensive strategy generation pipeline.
        
        Pipeline:
        1. Build stock idea
        2. Select and build option strategies based on market context
        3. Annotate with Greeks and field context
        4. Enhance with detailed risk metrics (PnL cones, breakevens, etc.)
        5. Apply exit rules (targets, stops, time-based)
        6. Apply Kelly-based position sizing
        7. Rank strategies using 6-factor composite scoring
        
        Args:
            ctx: Market context from Composer
            underlying_price: Current underlying price
            capital: Available capital (defaults to constructor value)
            implied_vol: Implied volatility for risk calculations (default 30%)
        
        Returns:
            Ranked list of TradeIdea objects with comprehensive risk metrics
        """
        cap = float(capital or self._default_capital)

        # 1) Build stock idea
        ideas: list[TradeIdea] = [build_stock_trade_idea(ctx)]

        # 2) Select and build option strategies
        builders = select_strategy_builders(ctx)
        for builder in builders:
            idea = builder(ctx, underlying_price)
            ideas.append(idea)

        # 3) Annotate with Greeks / field context
        ideas = [annotate_with_greeks_context(idea, ctx) for idea in ideas]

        # 4) Enhance with detailed risk metrics (NEW)
        ideas = [
            enhance_idea_with_risk_metrics(idea, underlying_price, implied_vol)
            for idea in ideas
        ]

        # 5) Apply exit rules (NEW)
        ideas = self._apply_exit_rules(ideas, ctx.confidence)

        # 6) Apply Kelly-based sizing
        ideas = apply_risk_and_sizing(ideas, ctx, capital=cap)

        # 7) Rank strategies (Phase 6: Strategy Ranking Engine v1.0)
        ideas = self._ranking_engine.rank(ideas, ctx, max_capital=cap)

        return ideas

    def _apply_exit_rules(
        self,
        ideas: list[TradeIdea],
        confidence: float,
    ) -> list[TradeIdea]:
        """Apply exit rules to each trade idea."""
        
        for idea in ideas:
            exit_rules = create_default_exit_rules(
                strategy_type=idea.strategy_type,
                confidence=confidence,
            )
            
            # Attach exit parameters to the idea
            idea.profit_target_pct = exit_rules.profit_target_pct
            idea.stop_loss_pct = exit_rules.stop_loss_pct
            idea.max_days_to_expiry = exit_rules.max_days_to_expiry
            idea.trailing_stop_pct = exit_rules.trailing_stop_pct
        
        return ideas
