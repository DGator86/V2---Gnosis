# tests/optimizer/test_kelly_refinement.py

"""Tests for Kelly Criterion refinement."""

import pytest
import math

from optimizer.kelly_refinement import (
    compute_kelly_fraction,
    clamp_kelly_fraction,
    recommended_risk_fraction,
)


class TestComputeKellyFraction:
    """Test raw Kelly fraction computation."""
    
    def test_basic_kelly(self):
        """Test basic Kelly with positive edge."""
        # Win rate 60%, avg win = avg loss
        kelly = compute_kelly_fraction(
            win_rate=0.6,
            avg_win=100,
            avg_loss=100,
        )
        
        # Kelly = (bp - q) / b where b=1, p=0.6, q=0.4
        # Kelly = (1*0.6 - 0.4) / 1 = 0.2
        assert abs(kelly - 0.2) < 0.01
    
    def test_kelly_symmetric_payoff(self):
        """Test Kelly with symmetric 1:1 payoff."""
        kelly = compute_kelly_fraction(
            win_rate=0.55,
            avg_win=100,
            avg_loss=100,
        )
        
        # Kelly = (1*0.55 - 0.45) / 1 = 0.10
        assert abs(kelly - 0.10) < 0.01
    
    def test_kelly_asymmetric_payoff(self):
        """Test Kelly with asymmetric payoff (2:1)."""
        kelly = compute_kelly_fraction(
            win_rate=0.4,
            avg_win=200,
            avg_loss=100,
        )
        
        # b = 200/100 = 2, p=0.4, q=0.6
        # Kelly = (2*0.4 - 0.6) / 2 = (0.8 - 0.6) / 2 = 0.1
        assert abs(kelly - 0.1) < 0.01
    
    def test_kelly_negative_edge(self):
        """Test Kelly with negative edge (losing strategy)."""
        kelly = compute_kelly_fraction(
            win_rate=0.3,
            avg_win=100,
            avg_loss=100,
        )
        
        # Kelly = (1*0.3 - 0.7) / 1 = -0.4 (negative edge)
        assert kelly < 0
    
    def test_kelly_50_50(self):
        """Test Kelly with no edge (50/50)."""
        kelly = compute_kelly_fraction(
            win_rate=0.5,
            avg_win=100,
            avg_loss=100,
        )
        
        # Kelly = (1*0.5 - 0.5) / 1 = 0 (no edge)
        assert abs(kelly) < 0.01
    
    def test_kelly_high_win_rate(self):
        """Test Kelly with high win rate."""
        kelly = compute_kelly_fraction(
            win_rate=0.75,
            avg_win=100,
            avg_loss=100,
        )
        
        # Kelly = (1*0.75 - 0.25) / 1 = 0.5
        assert abs(kelly - 0.5) < 0.01
    
    def test_kelly_invalid_avg_loss(self):
        """Test Kelly raises error for invalid avg_loss."""
        with pytest.raises(ValueError, match="avg_loss must be positive"):
            compute_kelly_fraction(0.6, 100, 0)
        
        with pytest.raises(ValueError, match="avg_loss must be positive"):
            compute_kelly_fraction(0.6, 100, -50)
    
    def test_kelly_extreme_win_rate(self):
        """Test Kelly with extreme win rates."""
        # Win rate = 0 (always loses)
        kelly_zero = compute_kelly_fraction(0.0, 100, 100)
        assert kelly_zero == 0.0
        
        # Win rate = 1 (always wins)
        kelly_one = compute_kelly_fraction(1.0, 100, 100)
        assert kelly_one == 0.0  # Degenerate case


class TestClampKellyFraction:
    """Test Kelly fraction clamping."""
    
    def test_clamp_within_range(self):
        """Test clamping value within range."""
        clamped = clamp_kelly_fraction(0.15, max_fraction=0.25, min_fraction=-0.25)
        
        assert clamped == 0.15  # Unchanged
    
    def test_clamp_above_max(self):
        """Test clamping value above max."""
        clamped = clamp_kelly_fraction(0.40, max_fraction=0.25, min_fraction=-0.25)
        
        assert clamped == 0.25  # Clamped to max
    
    def test_clamp_below_min(self):
        """Test clamping value below min."""
        clamped = clamp_kelly_fraction(-0.35, max_fraction=0.25, min_fraction=-0.25)
        
        assert clamped == -0.25  # Clamped to min
    
    def test_clamp_default_limits(self):
        """Test default clamp limits."""
        clamped = clamp_kelly_fraction(0.50)
        
        assert clamped == 0.25  # Default max is 0.25
    
    def test_clamp_negative_kelly(self):
        """Test clamping negative Kelly."""
        clamped = clamp_kelly_fraction(-0.10, max_fraction=0.25, min_fraction=-0.25)
        
        assert clamped == -0.10  # Within range


class TestRecommendedRiskFraction:
    """Test recommended risk fraction calculation."""
    
    def test_basic_risk_fraction(self):
        """Test basic risk fraction with positive edge."""
        risk = recommended_risk_fraction(
            empirical_win_rate=0.6,
            avg_win=100,
            avg_loss=100,
            confidence=1.0,
            global_risk_cap=0.02,
        )
        
        # Kelly = 0.2 (clamped to 0.2)
        # risk = 0.2 * 1.0 * 0.02 = 0.004 (0.4% of account)
        assert abs(risk - 0.004) < 0.001
    
    def test_risk_fraction_with_confidence(self):
        """Test risk fraction scales with confidence."""
        risk_high = recommended_risk_fraction(
            empirical_win_rate=0.6,
            avg_win=100,
            avg_loss=100,
            confidence=1.0,
            global_risk_cap=0.02,
        )
        
        risk_low = recommended_risk_fraction(
            empirical_win_rate=0.6,
            avg_win=100,
            avg_loss=100,
            confidence=0.5,
            global_risk_cap=0.02,
        )
        
        # Low confidence should result in smaller risk
        assert risk_low < risk_high
        assert abs(risk_low - risk_high / 2) < 0.001
    
    def test_risk_fraction_obeys_global_cap(self):
        """Test risk fraction respects global cap."""
        # Even with very high Kelly, should respect global_risk_cap
        risk = recommended_risk_fraction(
            empirical_win_rate=0.9,
            avg_win=200,
            avg_loss=50,
            confidence=1.0,
            global_risk_cap=0.01,  # 1% max per trade
        )
        
        # Should never exceed global_risk_cap
        assert risk <= 0.01
    
    def test_risk_fraction_with_clamped_kelly(self):
        """Test risk fraction when Kelly is clamped."""
        # Very high theoretical Kelly (>0.25)
        risk = recommended_risk_fraction(
            empirical_win_rate=0.8,
            avg_win=300,
            avg_loss=50,
            confidence=1.0,
            global_risk_cap=0.02,
        )
        
        # Kelly should be clamped to 0.25
        # risk = 0.25 * 1.0 * 0.02 = 0.005
        assert abs(risk - 0.005) < 0.001
    
    def test_risk_fraction_zero_edge(self):
        """Test risk fraction with no edge."""
        risk = recommended_risk_fraction(
            empirical_win_rate=0.5,
            avg_win=100,
            avg_loss=100,
            confidence=0.8,
            global_risk_cap=0.02,
        )
        
        # Kelly = 0, risk should be ~0
        assert abs(risk) < 0.001
    
    def test_risk_fraction_negative_edge(self):
        """Test risk fraction with negative edge."""
        risk = recommended_risk_fraction(
            empirical_win_rate=0.3,
            avg_win=100,
            avg_loss=100,
            confidence=0.7,
            global_risk_cap=0.02,
        )
        
        # Kelly < 0, risk should be negative (or clamped to min)
        assert risk < 0


class TestIntegration:
    """Integration tests for Kelly refinement workflow."""
    
    def test_full_workflow(self):
        """Test complete Kelly refinement workflow."""
        # 1. Compute raw Kelly
        kelly = compute_kelly_fraction(0.55, 150, 100)
        
        # 2. Clamp Kelly
        clamped = clamp_kelly_fraction(kelly)
        
        # 3. Compute final risk
        risk = clamped * 0.8 * 0.02  # confidence=0.8, cap=2%
        
        assert risk > 0
        assert risk < 0.02  # Below global cap
    
    def test_conservative_sizing(self):
        """Test conservative position sizing."""
        risk = recommended_risk_fraction(
            empirical_win_rate=0.55,
            avg_win=100,
            avg_loss=100,
            confidence=0.5,  # Low confidence
            global_risk_cap=0.01,  # Conservative cap
        )
        
        # Should result in very small position
        assert risk < 0.001  # < 0.1% of account
