# agents/trade_agent/sizing_engine.py

from __future__ import annotations

from typing import Iterable, List

from pydantic import BaseModel, Field

from .schemas import ComposerTradeContext, TradeIdea, StrategyType


class SizingConfig(BaseModel):
    """
    Configuration for sizing and risk.
    This is stateless, purely parameterizes behavior.
    """

    max_capital: float = Field(..., gt=0.0)

    # Hard caps as fraction of equity
    max_risk_per_trade: float = Field(0.01, gt=0.0, le=0.1)      # 1% default
    max_portfolio_risk: float = Field(0.05, gt=0.0, le=0.5)      # 5% default

    # Kelly-related parameters
    kelly_scale: float = Field(0.5, ge=0.0, le=1.0)              # 0.5 = half-Kelly
    base_win_loss_ratio: float = Field(1.5, gt=0.1)              # R ~1.5 default

    # Optional: clamp confidence so it never becomes a ridiculous "probability"
    min_confidence: float = Field(0.45, ge=0.0, le=0.5)
    max_confidence: float = Field(0.80, ge=0.5, le=1.0)


class SizingEngine:
    """
    Stateless Sizing Engine:
    - Consumes TradeIdeas + ComposerTradeContext
    - Outputs the same ideas with max_risk, total_cost, recommended_size,
      and ranking_score filled in.

    No memory, no PnL tracking. Pure function of (ideas, ctx, config).
    """

    def __init__(self, config: SizingConfig):
        self._cfg = config

    def size_ideas(
        self,
        ideas: Iterable[TradeIdea],
        ctx: ComposerTradeContext,
        existing_portfolio_risk: float = 0.0,
    ) -> List[TradeIdea]:
        """
        existing_portfolio_risk: optional fraction of capital already at risk (0–1),
        so external systems can clamp further. For now, default 0 to remain stateless.
        """
        ideas = list(ideas)
        available_risk = max(
            0.0,
            self._cfg.max_portfolio_risk - existing_portfolio_risk,
        )

        if available_risk <= 0.0:
            # If we are already at max portfolio risk, still return
            # ideas but with zero sizing; let caller decide.
            for idea in ideas:
                idea.max_risk = 0.0
                idea.total_cost = 0.0
                idea.recommended_size = 0
                idea.ranking_score = 0.0
            return ideas

        # Compute per-idea risk fractions and then scale if needed
        raw_fractions = [
            self._risk_fraction_for_idea(idea, ctx) for idea in ideas
        ]

        # Cap per trade and total
        capped_fractions = [
            min(self._cfg.max_risk_per_trade, rf) for rf in raw_fractions
        ]
        sum_capped = sum(capped_fractions) or 1e-9

        # Scale down if total exceeds available_risk
        scale = min(1.0, available_risk / sum_capped)
        final_fractions = [f * scale for f in capped_fractions]

        sized: list[TradeIdea] = []
        for idea, frac in zip(ideas, final_fractions):
            capital_at_risk = self._cfg.max_capital * frac

            idea.max_risk = capital_at_risk
            idea.total_cost = capital_at_risk  # placeholder until we have real prices
            idea.max_profit = capital_at_risk * self._expected_R_for_idea(idea, ctx)

            # Position size placeholder: one unit if any non-zero risk.
            idea.recommended_size = int(capital_at_risk > 0.0)

            # Ranking: combine confidence, liquidity, and allocated risk
            idea.ranking_score = (
                ctx.confidence * ctx.liquidity_score * (frac / self._cfg.max_risk_per_trade)
                if frac > 0.0
                else 0.0
            )

            sized.append(idea)

        # Sort in-place by ranking
        sized.sort(key=lambda x: (x.ranking_score or 0.0), reverse=True)
        return sized

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _risk_fraction_for_idea(
        self,
        idea: TradeIdea,
        ctx: ComposerTradeContext,
    ) -> float:
        """
        Compute a Kelly-style risk fraction from:
        - confidence (as a probability)
        - expected R multiple
        Then scaled and clamped by configuration.
        """
        p = self._confidence_to_probability(ctx.confidence)
        r = self._expected_R_for_idea(idea, ctx)

        # Kelly formula: f* = (p*(R+1) - 1) / R
        kelly_raw = (p * (r + 1.0) - 1.0) / max(r, 1e-6)
        kelly_raw = max(0.0, kelly_raw)  # no negative sizing

        kelly_scaled = kelly_raw * self._cfg.kelly_scale

        # Extra haircut if elastic energy is high (price harder to move)
        if ctx.elastic_energy > 1.5:
            kelly_scaled *= 0.5
        elif ctx.elastic_energy < 0.75:
            kelly_scaled *= 1.2

        # Return raw kelly_scaled; max_risk_per_trade will clamp in size_ideas()
        return max(0.0, kelly_scaled)

    def _confidence_to_probability(self, confidence: float) -> float:
        """
        Map 0–1 confidence → probability of success in Kelly formula.
        Never lets us pretend we have 99% certainty.
        """
        lo = self._cfg.min_confidence
        hi = self._cfg.max_confidence
        return max(lo, min(hi, confidence))

    def _expected_R_for_idea(
        self,
        idea: TradeIdea,
        ctx: ComposerTradeContext,
    ) -> float:
        """
        Coarse R multiple heuristic based on strategy type and expected move.
        This is intentionally simple. You can refine later with actual
        backtested payoff distributions.
        """
        base_R = self._cfg.base_win_loss_ratio

        # Adjust for expected move
        move_bonus = {
            "tiny": 0.3,
            "small": 0.5,
            "medium": 1.0,
            "large": 1.5,
            "explosive": 2.0,
        }[ctx.expected_move.value]

        # Strategy multiplier
        strat_mult = self._strategy_multiplier(idea.strategy_type)

        return max(0.5, base_R * move_bonus * strat_mult)

    @staticmethod
    def _strategy_multiplier(strategy_type: StrategyType) -> float:
        """
        Long convex strategies get higher R potential, income strategies lower.
        """
        if strategy_type in {
            StrategyType.LONG_CALL,
            StrategyType.LONG_PUT,
            StrategyType.STRADDLE,
            StrategyType.STRANGLE,
        }:
            return 1.5
        if strategy_type in {
            StrategyType.CALL_DEBIT_SPREAD,
            StrategyType.PUT_DEBIT_SPREAD,
        }:
            return 1.0
        if strategy_type in {
            StrategyType.IRON_CONDOR,
            StrategyType.CALENDAR_SPREAD,
            StrategyType.DIAGONAL_SPREAD,
            StrategyType.BROKEN_WING_BUTTERFLY,
            StrategyType.REVERSE_IRON_CONDOR,
        }:
            return 0.7
        if strategy_type == StrategyType.STOCK:
            return 0.8
        return 1.0
