# tests/agents/test_trade_agent_v2.py

from __future__ import annotations

import pytest

from agents.trade_agent.schemas import (
    ComposerTradeContext,
    Direction,
    ExpectedMove,
    StrategyType,
    Timeframe,
    VolatilityRegime,
)
from agents.trade_agent.trade_agent_v2 import TradeAgentV2


def _sample_ctx(
    direction: Direction = Direction.BULLISH,
    vol_regime: VolatilityRegime = VolatilityRegime.MID,
) -> ComposerTradeContext:
    return ComposerTradeContext(
        asset="SPY",
        direction=direction,
        confidence=0.7,
        expected_move=ExpectedMove.MEDIUM,
        volatility_regime=vol_regime,
        timeframe=Timeframe.SWING,
        elastic_energy=1.5,
        gamma_exposure=-1.0,
        vanna_exposure=0.5,
        charm_exposure=-0.3,
        liquidity_score=0.9,
    )


class TestTradeAgentBasicFunctionality:
    """Test core Trade Agent behavior."""

    def test_trade_agent_returns_non_empty_ideas_for_bullish(self):
        agent = TradeAgentV2(default_capital=10_000)
        ctx = _sample_ctx(Direction.BULLISH)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        assert len(ideas) >= 2  # stock + at least one option
        # ensure they are ranked
        scores = [i.ranking_score for i in ideas]
        assert scores == sorted(scores, reverse=True)

    def test_trade_agent_returns_ideas_for_bearish(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BEARISH)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        assert len(ideas) >= 2
        strategy_types = {i.strategy_type.value for i in ideas}
        assert "stock" in strategy_types

    def test_trade_agent_includes_stock_idea_always(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.NEUTRAL)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        stock_ideas = [i for i in ideas if i.strategy_type == StrategyType.STOCK]
        assert len(stock_ideas) == 1

    def test_all_ideas_have_confidence_and_asset(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        for idea in ideas:
            assert idea.asset == "SPY"
            assert 0.0 <= idea.confidence <= 1.0
            assert idea.description is not None


class TestStrategySelection:
    """Test that correct strategies are selected based on context."""

    def test_neutral_uses_iron_condor(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.NEUTRAL)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)
        strategy_types = {i.strategy_type.value for i in ideas}

        assert "iron_condor" in strategy_types

    def test_bullish_includes_call_strategies(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)
        strategy_types = {i.strategy_type.value for i in ideas}

        # Should have at least one call strategy
        call_strategies = {"long_call", "call_debit_spread"}
        assert len(call_strategies & strategy_types) > 0

    def test_bearish_includes_put_strategies(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BEARISH)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)
        strategy_types = {i.strategy_type.value for i in ideas}

        # Should have at least one put strategy
        put_strategies = {"long_put", "put_debit_spread"}
        assert len(put_strategies & strategy_types) > 0

    def test_vol_expansion_includes_straddle_and_strangle(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH, VolatilityRegime.VOL_EXPANSION)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)
        strategy_types = {i.strategy_type.value for i in ideas}

        assert "straddle" in strategy_types
        assert "strangle" in strategy_types

    def test_vol_crush_includes_iron_condor(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH, VolatilityRegime.VOL_CRUSH)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)
        strategy_types = {i.strategy_type.value for i in ideas}

        assert "iron_condor" in strategy_types


class TestGreeksAnnotation:
    """Test Greeks context is added to notes."""

    def test_negative_gamma_annotated_in_notes(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH)
        ctx.gamma_exposure = -1.5

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        # At least one idea should have gamma annotation
        notes_combined = " ".join([i.notes or "" for i in ideas])
        assert "gamma" in notes_combined.lower()

    def test_low_liquidity_annotated(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH)
        ctx.liquidity_score = 0.3

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        notes_combined = " ".join([i.notes or "" for i in ideas])
        assert "liquidity" in notes_combined.lower()


class TestRiskAndSizing:
    """Test risk calculations and position sizing."""

    def test_all_ideas_have_risk_metrics(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0, capital=10_000)

        for idea in ideas:
            assert idea.max_risk is not None
            assert idea.total_cost is not None
            assert idea.recommended_size is not None

    def test_higher_confidence_increases_risk_allocation(self):
        agent = TradeAgentV2()
        ctx_low = _sample_ctx(Direction.BULLISH)
        ctx_low.confidence = 0.3

        ctx_high = _sample_ctx(Direction.BULLISH)
        ctx_high.confidence = 0.9

        ideas_low = agent.generate_trade_ideas(ctx_low, underlying_price=500.0, capital=10_000)
        ideas_high = agent.generate_trade_ideas(ctx_high, underlying_price=500.0, capital=10_000)

        # Average risk should be higher for high confidence
        avg_risk_low = sum(i.max_risk or 0 for i in ideas_low) / len(ideas_low)
        avg_risk_high = sum(i.max_risk or 0 for i in ideas_high) / len(ideas_high)

        assert avg_risk_high > avg_risk_low

    def test_ranking_score_populated(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        for idea in ideas:
            assert idea.ranking_score is not None
            assert idea.ranking_score >= 0


class TestStatelessness:
    """Verify agent is truly stateless."""

    def test_multiple_calls_produce_same_results(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH)

        ideas1 = agent.generate_trade_ideas(ctx, underlying_price=500.0)
        ideas2 = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        assert len(ideas1) == len(ideas2)
        # Strategy types should be identical
        types1 = [i.strategy_type for i in ideas1]
        types2 = [i.strategy_type for i in ideas2]
        assert types1 == types2

    def test_changing_context_changes_output(self):
        agent = TradeAgentV2()
        ctx_bullish = _sample_ctx(Direction.BULLISH)
        ctx_bearish = _sample_ctx(Direction.BEARISH)

        ideas_bull = agent.generate_trade_ideas(ctx_bullish, underlying_price=500.0)
        ideas_bear = agent.generate_trade_ideas(ctx_bearish, underlying_price=500.0)

        types_bull = {i.strategy_type.value for i in ideas_bull}
        types_bear = {i.strategy_type.value for i in ideas_bear}

        # Should have different strategy sets
        assert types_bull != types_bear


class TestOptionLegs:
    """Test option leg structure for multi-leg strategies."""

    def test_iron_condor_has_four_legs(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.NEUTRAL)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        ic_ideas = [i for i in ideas if i.strategy_type == StrategyType.IRON_CONDOR]
        assert len(ic_ideas) > 0

        for ic in ic_ideas:
            assert len(ic.legs) == 4
            # Should have 2 puts and 2 calls
            puts = [leg for leg in ic.legs if leg.option_type == "put"]
            calls = [leg for leg in ic.legs if leg.option_type == "call"]
            assert len(puts) == 2
            assert len(calls) == 2

    def test_straddle_has_two_legs(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH, VolatilityRegime.VOL_EXPANSION)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        straddle_ideas = [i for i in ideas if i.strategy_type == StrategyType.STRADDLE]
        assert len(straddle_ideas) > 0

        for straddle in straddle_ideas:
            assert len(straddle.legs) == 2
            # One call, one put
            puts = [leg for leg in straddle.legs if leg.option_type == "put"]
            calls = [leg for leg in straddle.legs if leg.option_type == "call"]
            assert len(puts) == 1
            assert len(calls) == 1

    def test_all_legs_have_required_fields(self):
        agent = TradeAgentV2()
        ctx = _sample_ctx(Direction.BULLISH, VolatilityRegime.VOL_EXPANSION)

        ideas = agent.generate_trade_ideas(ctx, underlying_price=500.0)

        for idea in ideas:
            for leg in idea.legs:
                assert leg.side in ["long", "short"]
                assert leg.option_type in ["call", "put"]
                assert leg.strike > 0
                assert leg.expiry is not None
                assert leg.quantity > 0
