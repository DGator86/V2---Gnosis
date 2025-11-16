# tests/optimizer/test_historical_evaluator.py

"""Tests for regime-based performance evaluation."""

import pytest
import math

from optimizer.historical_evaluator import (
    RegimeKey,
    TradeOutcome,
    RegimeStats,
    compute_regime_stats,
    pick_best_regimes,
)


@pytest.fixture
def sample_regimes():
    """Create sample regime keys."""
    return {
        "high_vol_up": RegimeKey("high", "up", "short_gamma", "normal"),
        "low_vol_down": RegimeKey("low", "down", "long_gamma", "thin"),
        "mid_vol_sideways": RegimeKey("mid", "sideways", "neutral", "deep"),
    }


@pytest.fixture
def sample_trades(sample_regimes):
    """Create sample trade outcomes."""
    trades = []
    
    # High vol uptrend: 10 trades, 70% win rate
    for i in range(10):
        pnl = 100 if i < 7 else -50
        trades.append(TradeOutcome(
            regime=sample_regimes["high_vol_up"],
            pnl=pnl,
            is_win=pnl > 0,
            max_drawdown=20 if pnl < 0 else 5,
        ))
    
    # Low vol downtrend: 5 trades, 40% win rate
    for i in range(5):
        pnl = 50 if i < 2 else -30
        trades.append(TradeOutcome(
            regime=sample_regimes["low_vol_down"],
            pnl=pnl,
            is_win=pnl > 0,
            max_drawdown=15,
        ))
    
    # Mid vol sideways: 3 trades
    for i in range(3):
        trades.append(TradeOutcome(
            regime=sample_regimes["mid_vol_sideways"],
            pnl=20 if i < 2 else -10,
            is_win=i < 2,
            max_drawdown=5,
        ))
    
    return trades


class TestRegimeKey:
    """Test RegimeKey immutability and equality."""
    
    def test_regime_key_frozen(self):
        """Test RegimeKey is frozen (immutable)."""
        key = RegimeKey("high", "up", "short_gamma", "normal")
        
        with pytest.raises(AttributeError):
            key.vix_bucket = "low"  # Should fail
    
    def test_regime_key_hashable(self):
        """Test RegimeKey can be used as dict key."""
        key1 = RegimeKey("high", "up", "short_gamma", "normal")
        key2 = RegimeKey("high", "up", "short_gamma", "normal")
        key3 = RegimeKey("low", "down", "long_gamma", "thin")
        
        d = {key1: "value1"}
        assert d[key2] == "value1"  # Same key
        assert key3 not in d


class TestTradeOutcome:
    """Test TradeOutcome data structure."""
    
    def test_trade_outcome_creation(self, sample_regimes):
        """Test creating trade outcome."""
        regime = sample_regimes["high_vol_up"]
        trade = TradeOutcome(
            regime=regime,
            pnl=150.0,
            is_win=True,
            max_drawdown=10.0,
        )
        
        assert trade.regime == regime
        assert trade.pnl == 150.0
        assert trade.is_win is True
        assert trade.max_drawdown == 10.0


class TestComputeRegimeStats:
    """Test regime statistics computation."""
    
    def test_compute_stats_basic(self, sample_trades, sample_regimes):
        """Test basic regime stats computation."""
        stats = compute_regime_stats(sample_trades)
        
        assert len(stats) == 3
        assert sample_regimes["high_vol_up"] in stats
        assert sample_regimes["low_vol_down"] in stats
        assert sample_regimes["mid_vol_sideways"] in stats
    
    def test_high_vol_up_stats(self, sample_trades, sample_regimes):
        """Test stats for high vol uptrend regime."""
        stats = compute_regime_stats(sample_trades)
        
        high_vol_stats = stats[sample_regimes["high_vol_up"]]
        
        assert high_vol_stats.count == 10
        assert high_vol_stats.win_rate == 0.7
        assert high_vol_stats.avg_pnl > 0  # Net positive
    
    def test_low_vol_down_stats(self, sample_trades, sample_regimes):
        """Test stats for low vol downtrend regime."""
        stats = compute_regime_stats(sample_trades)
        
        low_vol_stats = stats[sample_regimes["low_vol_down"]]
        
        assert low_vol_stats.count == 5
        assert low_vol_stats.win_rate == 0.4
    
    def test_avg_pnl_calculation(self, sample_regimes):
        """Test average PnL calculation."""
        trades = [
            TradeOutcome(sample_regimes["high_vol_up"], 100, True),
            TradeOutcome(sample_regimes["high_vol_up"], -50, False),
            TradeOutcome(sample_regimes["high_vol_up"], 150, True),
        ]
        
        stats = compute_regime_stats(trades)
        regime_stats = stats[sample_regimes["high_vol_up"]]
        
        expected_avg = (100 - 50 + 150) / 3
        assert abs(regime_stats.avg_pnl - expected_avg) < 0.01
    
    def test_pnl_std_calculation(self, sample_regimes):
        """Test PnL standard deviation calculation."""
        trades = [
            TradeOutcome(sample_regimes["high_vol_up"], 100, True),
            TradeOutcome(sample_regimes["high_vol_up"], 100, True),
            TradeOutcome(sample_regimes["high_vol_up"], 100, True),
        ]
        
        stats = compute_regime_stats(trades)
        regime_stats = stats[sample_regimes["high_vol_up"]]
        
        # No variance - all same PnL
        assert regime_stats.pnl_std < 0.01
    
    def test_avg_max_drawdown(self, sample_regimes):
        """Test average max drawdown calculation."""
        trades = [
            TradeOutcome(sample_regimes["high_vol_up"], 100, True, max_drawdown=10),
            TradeOutcome(sample_regimes["high_vol_up"], -50, False, max_drawdown=30),
            TradeOutcome(sample_regimes["high_vol_up"], 150, True, max_drawdown=5),
        ]
        
        stats = compute_regime_stats(trades)
        regime_stats = stats[sample_regimes["high_vol_up"]]
        
        expected_avg_dd = (10 + 30 + 5) / 3
        assert abs(regime_stats.avg_max_drawdown - expected_avg_dd) < 0.01


class TestPickBestRegimes:
    """Test regime filtering and ranking."""
    
    def test_filter_by_min_trades(self, sample_trades):
        """Test filtering regimes by minimum trade count."""
        stats = compute_regime_stats(sample_trades)
        
        # Filter for at least 5 trades
        best = pick_best_regimes(stats, min_trades=5, sort_by="count")
        
        # Should include high_vol_up (10) and low_vol_down (5)
        # Should exclude mid_vol_sideways (3)
        assert len(best) == 2
    
    def test_sort_by_avg_pnl(self, sample_trades):
        """Test sorting by average PnL."""
        stats = compute_regime_stats(sample_trades)
        
        best = pick_best_regimes(stats, min_trades=1, sort_by="avg_pnl")
        
        # Should be sorted descending by avg_pnl
        for i in range(len(best) - 1):
            assert best[i][1].avg_pnl >= best[i + 1][1].avg_pnl
    
    def test_sort_by_win_rate(self, sample_trades):
        """Test sorting by win rate."""
        stats = compute_regime_stats(sample_trades)
        
        best = pick_best_regimes(stats, min_trades=1, sort_by="win_rate")
        
        # Should be sorted descending by win_rate
        for i in range(len(best) - 1):
            assert best[i][1].win_rate >= best[i + 1][1].win_rate
    
    def test_sort_by_count(self, sample_trades):
        """Test sorting by trade count."""
        stats = compute_regime_stats(sample_trades)
        
        best = pick_best_regimes(stats, min_trades=1, sort_by="count")
        
        # Should be sorted descending by count
        for i in range(len(best) - 1):
            assert best[i][1].count >= best[i + 1][1].count
    
    def test_empty_trades(self):
        """Test handling empty trade list."""
        stats = compute_regime_stats([])
        
        assert len(stats) == 0
        
        best = pick_best_regimes(stats)
        assert len(best) == 0
