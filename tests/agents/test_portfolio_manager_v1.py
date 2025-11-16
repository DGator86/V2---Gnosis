# tests/agents/test_portfolio_manager_v1.py

from __future__ import annotations

import pytest

from agents.portfolio.portfolio_manager_v1 import PortfolioManagerV1
from agents.portfolio.risk_limits import PortfolioRiskLimits
from agents.portfolio.schemas import PortfolioState, Position, PositionSide
from agents.trade_agent.schemas import StrategyType, TradeIdea


def _portfolio_empty(equity: float = 100_000.0) -> PortfolioState:
    return PortfolioState(
        equity=equity,
        cash=equity,
        positions=[],
    )


def _idea(
    asset: str,
    strategy_type: StrategyType,
    max_risk: float,
    ranking_score: float,
    recommended_size: int = 1,
) -> TradeIdea:
    return TradeIdea(
        asset=asset,
        strategy_type=strategy_type,
        description="test",
        legs=[],
        total_cost=max_risk,
        max_risk=max_risk,
        recommended_size=recommended_size,
        confidence=0.7,
        ranking_score=ranking_score,
    )


class TestPortfolioManagerBasics:
    """Test core Portfolio Manager functionality."""

    def test_portfolio_manager_opens_ideas_until_risk_cap(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.10,  # 10% of equity
            max_risk_per_trade=0.05,  # 5% per trade
            max_risk_per_asset=0.10,
            max_open_positions=10,
        )
        mgr = PortfolioManagerV1(risk_limits=limits)

        portfolio = _portfolio_empty(equity=100_000.0)

        # Three ideas with 3% risk each
        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 3_000.0, 0.9),
            _idea("SPY", StrategyType.IRON_CONDOR, 3_000.0, 0.8),
            _idea("QQQ", StrategyType.LONG_CALL, 3_000.0, 0.7),
            _idea("IWM", StrategyType.LONG_CALL, 3_000.0, 0.6),
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # 10% of 100k = 10k; each idea is 3k risk, so at most 3 trades
        assert 2 <= len(plan) <= 3
        for order in plan:
            assert order.notional_risk <= limits.max_risk_per_trade * portfolio.equity

    def test_per_asset_cap_enforced(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.50,
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.10,  # 10% per asset
            max_open_positions=10,
            default_strategy_cap=0.20,  # Allow strategy risk up to 20%
        )
        mgr = PortfolioManagerV1(risk_limits=limits)
        portfolio = _portfolio_empty(equity=100_000.0)

        # Two big SPY ideas (10% each) + one QQQ
        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 10_000.0, 0.9),
            _idea("SPY", StrategyType.IRON_CONDOR, 10_000.0, 0.8),
            _idea("QQQ", StrategyType.LONG_CALL, 10_000.0, 0.7),
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)
        spy_orders = [o for o in plan if o.asset == "SPY"]
        qqq_orders = [o for o in plan if o.asset == "QQQ"]

        # Only 1 SPY allowed (10% per asset), but QQQ allowed
        assert len(spy_orders) == 1
        assert len(qqq_orders) == 1

    def test_max_open_positions_enforced(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.50,
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.50,
            max_open_positions=1,
        )
        mgr = PortfolioManagerV1(risk_limits=limits)
        portfolio = _portfolio_empty(equity=100_000.0)

        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 5_000.0, 0.9),
            _idea("QQQ", StrategyType.LONG_CALL, 5_000.0, 0.8),
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)
        assert len(plan) == 1
        assert plan[0].asset == "SPY"  # highest-ranked

    def test_existing_positions_count_toward_limits(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.20,
            max_risk_per_trade=0.05,
            max_risk_per_asset=0.20,
            max_open_positions=2,
            default_strategy_cap=0.20,  # Allow higher strategy risk
        )
        mgr = PortfolioManagerV1(risk_limits=limits)

        portfolio = PortfolioState(
            equity=100_000.0,
            cash=90_000.0,
            positions=[
                Position(
                    asset="SPY",
                    strategy_type=StrategyType.LONG_CALL,
                    side=PositionSide.LONG,
                    size=1,
                    entry_price=10.0,
                    current_price=12.0,
                    max_risk_allocated=5_000.0,
                    unrealized_pnl=2_000.0,
                )
            ],
        )

        ideas = [
            _idea("QQQ", StrategyType.LONG_CALL, 5_000.0, 0.9),
            _idea("IWM", StrategyType.LONG_CALL, 5_000.0, 0.8),
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # Only 1 more position allowed (max_open_positions=2)
        assert len(plan) == 1


class TestRankingScoreOrdering:
    """Test that ideas are consumed in ranking_score order."""

    def test_highest_ranked_idea_selected_first(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.10,
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.50,
            max_open_positions=1,
        )
        mgr = PortfolioManagerV1(risk_limits=limits)
        portfolio = _portfolio_empty(equity=100_000.0)

        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 5_000.0, 0.5),  # Low rank
            _idea("QQQ", StrategyType.LONG_CALL, 5_000.0, 0.95),  # High rank
            _idea("IWM", StrategyType.LONG_CALL, 5_000.0, 0.7),  # Mid rank
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # Should select QQQ (highest rank)
        assert len(plan) == 1
        assert plan[0].asset == "QQQ"
        assert plan[0].source_idea.ranking_score == 0.95

    def test_zero_ranking_score_ideas_excluded(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.50,
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.50,
            max_open_positions=10,
        )
        mgr = PortfolioManagerV1(risk_limits=limits)
        portfolio = _portfolio_empty(equity=100_000.0)

        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 5_000.0, 0.0),  # Zero rank
            _idea("QQQ", StrategyType.LONG_CALL, 5_000.0, 0.8),  # Valid rank
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # Only QQQ should be included
        assert len(plan) == 1
        assert plan[0].asset == "QQQ"


class TestPerStrategyRiskCaps:
    """Test per-strategy risk limits."""

    def test_per_strategy_cap_enforced(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.50,
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.50,
            max_open_positions=10,
            max_risk_by_strategy={
                StrategyType.LONG_CALL: 0.10,  # 10% max for long calls
            },
            default_strategy_cap=0.20,
        )
        mgr = PortfolioManagerV1(risk_limits=limits)
        portfolio = _portfolio_empty(equity=100_000.0)

        # Two long call ideas (10% each)
        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 10_000.0, 0.9),
            _idea("QQQ", StrategyType.LONG_CALL, 10_000.0, 0.8),
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # Only 1 long call allowed (10% cap)
        assert len(plan) == 1
        assert plan[0].strategy_type == StrategyType.LONG_CALL

    def test_different_strategies_use_separate_caps(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.50,
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.50,
            max_open_positions=10,
            max_risk_by_strategy={
                StrategyType.LONG_CALL: 0.10,  # 10% max
                StrategyType.IRON_CONDOR: 0.15,  # 15% max
            },
        )
        mgr = PortfolioManagerV1(risk_limits=limits)
        portfolio = _portfolio_empty(equity=100_000.0)

        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 10_000.0, 0.9),  # Uses long_call cap
            _idea("QQQ", StrategyType.IRON_CONDOR, 10_000.0, 0.8),  # Uses condor cap
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # Both should be allowed (separate caps)
        assert len(plan) == 2


class TestExistingPositionAccounting:
    """Test that existing positions are accounted for in risk calculations."""

    def test_existing_position_counts_toward_portfolio_risk(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.15,  # 15% total
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.50,
            max_open_positions=10,
            default_strategy_cap=0.20,  # Allow higher strategy risk
        )
        mgr = PortfolioManagerV1(risk_limits=limits)

        # Portfolio with 10% risk already allocated
        portfolio = PortfolioState(
            equity=100_000.0,
            cash=90_000.0,
            positions=[
                Position(
                    asset="SPY",
                    strategy_type=StrategyType.LONG_CALL,
                    side=PositionSide.LONG,
                    size=1,
                    entry_price=10.0,
                    current_price=12.0,
                    max_risk_allocated=10_000.0,  # 10% of equity
                    unrealized_pnl=2_000.0,
                )
            ],
        )

        ideas = [
            _idea("QQQ", StrategyType.LONG_CALL, 8_000.0, 0.9),  # Would exceed 15% total
            _idea("IWM", StrategyType.LONG_CALL, 4_000.0, 0.8),  # Fits within 15%
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # Only IWM should fit (10% existing + 4% = 14% < 15%)
        assert len(plan) == 1
        assert plan[0].asset == "IWM"

    def test_existing_position_counts_toward_asset_risk(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.50,
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.15,  # 15% per asset
            max_open_positions=10,
            default_strategy_cap=0.20,  # Allow higher strategy risk
        )
        mgr = PortfolioManagerV1(risk_limits=limits)

        # Existing SPY position with 10% risk
        portfolio = PortfolioState(
            equity=100_000.0,
            cash=90_000.0,
            positions=[
                Position(
                    asset="SPY",
                    strategy_type=StrategyType.LONG_CALL,
                    side=PositionSide.LONG,
                    size=1,
                    entry_price=10.0,
                    current_price=12.0,
                    max_risk_allocated=10_000.0,
                    unrealized_pnl=2_000.0,
                )
            ],
        )

        ideas = [
            _idea("SPY", StrategyType.IRON_CONDOR, 8_000.0, 0.9),  # Would exceed 15% SPY
            _idea("QQQ", StrategyType.LONG_CALL, 8_000.0, 0.8),  # Different asset
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # SPY idea rejected (10% + 8% > 15%), QQQ allowed
        assert len(plan) == 1
        assert plan[0].asset == "QQQ"

    def test_existing_position_counts_toward_strategy_risk(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.50,
            max_risk_per_trade=0.10,
            max_risk_per_asset=0.50,
            max_open_positions=10,
            max_risk_by_strategy={
                StrategyType.LONG_CALL: 0.15,  # 15% max for long calls
            },
            default_strategy_cap=0.20,  # Allow higher for other strategies
        )
        mgr = PortfolioManagerV1(risk_limits=limits)

        # Existing long call with 10% risk
        portfolio = PortfolioState(
            equity=100_000.0,
            cash=90_000.0,
            positions=[
                Position(
                    asset="SPY",
                    strategy_type=StrategyType.LONG_CALL,
                    side=PositionSide.LONG,
                    size=1,
                    entry_price=10.0,
                    current_price=12.0,
                    max_risk_allocated=10_000.0,
                    unrealized_pnl=2_000.0,
                )
            ],
        )

        ideas = [
            _idea("QQQ", StrategyType.LONG_CALL, 8_000.0, 0.9),  # Would exceed 15%
            _idea("IWM", StrategyType.IRON_CONDOR, 8_000.0, 0.8),  # Different strategy
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # Long call rejected (10% + 8% > 15%), condor allowed
        assert len(plan) == 1
        assert plan[0].strategy_type == StrategyType.IRON_CONDOR


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_equity_returns_empty_plan(self):
        limits = PortfolioRiskLimits()
        mgr = PortfolioManagerV1(risk_limits=limits)

        portfolio = PortfolioState(equity=0.0, cash=0.0, positions=[])
        ideas = [_idea("SPY", StrategyType.LONG_CALL, 1_000.0, 0.9)]

        plan = mgr.build_execution_plan(portfolio, ideas)
        assert len(plan) == 0

    def test_zero_max_risk_ideas_excluded(self):
        limits = PortfolioRiskLimits(
            max_risk_per_trade=0.10,  # Allow 5% risk ideas
            default_strategy_cap=0.20  # Allow higher strategy risk
        )
        mgr = PortfolioManagerV1(risk_limits=limits)

        portfolio = _portfolio_empty(equity=100_000.0)
        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 0.0, 0.9),  # Zero risk
            _idea("QQQ", StrategyType.LONG_CALL, 5_000.0, 0.8),  # Valid
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)

        # Only QQQ included
        assert len(plan) == 1
        assert plan[0].asset == "QQQ"

    def test_empty_ideas_returns_empty_plan(self):
        limits = PortfolioRiskLimits()
        mgr = PortfolioManagerV1(risk_limits=limits)

        portfolio = _portfolio_empty(equity=100_000.0)
        ideas = []

        plan = mgr.build_execution_plan(portfolio, ideas)
        assert len(plan) == 0

    def test_all_ideas_exceed_limits_returns_empty_plan(self):
        limits = PortfolioRiskLimits(
            max_portfolio_risk=0.05,  # Very tight
            max_risk_per_trade=0.01,
            max_risk_per_asset=0.05,
            max_open_positions=1,
        )
        mgr = PortfolioManagerV1(risk_limits=limits)

        portfolio = _portfolio_empty(equity=100_000.0)
        ideas = [
            _idea("SPY", StrategyType.LONG_CALL, 10_000.0, 0.9),  # Too big (10%)
            _idea("QQQ", StrategyType.LONG_CALL, 8_000.0, 0.8),  # Too big (8%)
        ]

        plan = mgr.build_execution_plan(portfolio, ideas)
        assert len(plan) == 0


class TestOrderInstructionDetails:
    """Test that OrderInstruction fields are populated correctly."""

    def test_order_instruction_has_required_fields(self):
        limits = PortfolioRiskLimits(
            max_risk_per_trade=0.10,  # Allow 5% risk ideas
            default_strategy_cap=0.20  # Allow higher strategy risk
        )
        mgr = PortfolioManagerV1(risk_limits=limits)

        portfolio = _portfolio_empty(equity=100_000.0)
        ideas = [_idea("SPY", StrategyType.LONG_CALL, 5_000.0, 0.9)]

        plan = mgr.build_execution_plan(portfolio, ideas)

        assert len(plan) == 1
        order = plan[0]

        assert order.action == "open"
        assert order.asset == "SPY"
        assert order.strategy_type == StrategyType.LONG_CALL
        assert order.size_delta == 1
        assert order.notional_risk == 5_000.0
        assert "ranking_score" in order.reason
        assert order.source_idea is not None
        assert order.source_idea.asset == "SPY"
