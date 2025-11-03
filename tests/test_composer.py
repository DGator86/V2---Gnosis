from datetime import datetime
from gnosis.agents.agents_v1 import AgentView, compose

def test_alignment_long():
    """Test 2-of-3 alignment for long signal"""
    t = datetime(2025, 1, 1, 14, 31)
    views = [
        AgentView(
            symbol="SPY", bar=t, agent="hedge",
            dir_bias=1, confidence=0.7, thesis="breakout_up"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="liquidity",
            dir_bias=1, confidence=0.7, thesis="zone_follow"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="sentiment",
            dir_bias=-1, confidence=0.55, thesis="risk_off"
        )
    ]
    idea = compose("SPY", t, views, amihud=1e-10)  # Good liquidity
    
    assert idea["take_trade"] == True
    assert idea["direction"] == "long"
    assert idea["confidence"] > 0.5
    assert idea["position_sizing_hint"] > 0.5  # Good liquidity = larger size

def test_alignment_short():
    """Test 2-of-3 alignment for short signal"""
    t = datetime(2025, 1, 1, 14, 31)
    views = [
        AgentView(
            symbol="SPY", bar=t, agent="hedge",
            dir_bias=-1, confidence=0.65, thesis="breakout_down"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="liquidity",
            dir_bias=-1, confidence=0.75, thesis="resistance_dominant"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="sentiment",
            dir_bias=1, confidence=0.45, thesis="risk_on"
        )
    ]
    idea = compose("SPY", t, views, amihud=1e-10)
    
    assert idea["take_trade"] == True
    assert idea["direction"] == "short"

def test_no_alignment():
    """Test no trade when insufficient alignment"""
    t = datetime(2025, 1, 1, 14, 31)
    views = [
        AgentView(
            symbol="SPY", bar=t, agent="hedge",
            dir_bias=1, confidence=0.45, thesis="neutral_gamma"  # Low conf
        ),
        AgentView(
            symbol="SPY", bar=t, agent="liquidity",
            dir_bias=-1, confidence=0.55, thesis="zone_follow"  # Low conf
        ),
        AgentView(
            symbol="SPY", bar=t, agent="sentiment",
            dir_bias=0, confidence=0.50, thesis="regime_neutral"
        )
    ]
    idea = compose("SPY", t, views, amihud=1e-10)
    
    assert idea["take_trade"] == False
    assert "reason" in idea

def test_mixed_signals():
    """Test no trade with mixed strong signals"""
    t = datetime(2025, 1, 1, 14, 31)
    views = [
        AgentView(
            symbol="SPY", bar=t, agent="hedge",
            dir_bias=1, confidence=0.8, thesis="breakout_up"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="liquidity",
            dir_bias=-1, confidence=0.8, thesis="resistance_dominant"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="sentiment",
            dir_bias=1, confidence=0.3, thesis="regime_neutral"  # Weak tiebreaker
        )
    ]
    idea = compose("SPY", t, views, amihud=1e-10)
    
    # Should not take trade due to strong opposing signals
    assert idea["take_trade"] == False
    assert idea["reason"] in ["insufficient_alignment", "mixed_signals"]

def test_liquidity_sizing():
    """Test that illiquid markets get smaller size hints"""
    t = datetime(2025, 1, 1, 14, 31)
    views = [
        AgentView(
            symbol="SPY", bar=t, agent="hedge",
            dir_bias=1, confidence=0.7, thesis="breakout_up"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="liquidity",
            dir_bias=1, confidence=0.7, thesis="zone_follow"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="sentiment",
            dir_bias=1, confidence=0.65, thesis="risk_on"
        )
    ]
    
    # Liquid market
    idea_liquid = compose("SPY", t, views, amihud=1e-11)
    assert idea_liquid["take_trade"] == True
    size_liquid = idea_liquid["position_sizing_hint"]
    
    # Illiquid market
    idea_illiquid = compose("SPY", t, views, amihud=1e-8)
    assert idea_illiquid["take_trade"] == True
    size_illiquid = idea_illiquid["position_sizing_hint"]
    
    # Illiquid should have smaller size
    assert size_illiquid < size_liquid

def test_perfect_alignment():
    """Test strong signal when all agents agree with high confidence"""
    t = datetime(2025, 1, 1, 14, 31)
    views = [
        AgentView(
            symbol="SPY", bar=t, agent="hedge",
            dir_bias=1, confidence=0.85, thesis="breakout_up"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="liquidity",
            dir_bias=1, confidence=0.80, thesis="support_dominant"
        ),
        AgentView(
            symbol="SPY", bar=t, agent="sentiment",
            dir_bias=1, confidence=0.75, thesis="risk_on_follow"
        )
    ]
    idea = compose("SPY", t, views, amihud=5e-11)
    
    assert idea["take_trade"] == True
    assert idea["direction"] == "long"
    assert idea["confidence"] > 0.7  # High confidence with agreement
    assert idea["rationale"]["alignment"] == "3/3 agents agree"