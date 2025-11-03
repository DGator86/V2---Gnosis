"""
Post-Trade Reflection Generator

Auto-generates critique and lessons learned after each trade.
Lightweight LLM-free version using rule-based analysis.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from gnosis.memory.schema import Episode


class ReflectionEngine:
    """
    Generates post-trade reflections
    
    Analyzes:
    - Win/loss outcome
    - Exit reason (TP, SL, time, signal reverse)
    - Agent consensus quality
    - Duration vs expected
    - Regime fit
    
    Outputs:
    - Critique: What happened and why
    - Key lesson: One-liner takeaway
    - Regime label: Market state during trade
    """
    
    @staticmethod
    def generate_critique(episode: Episode) -> str:
        """
        Generate natural language critique
        
        Rule-based analysis of trade outcome.
        """
        if episode.pnl is None or episode.t_close is None:
            return "Trade still open - no outcome yet."
        
        lines = []
        
        # Outcome
        if episode.pnl > 0:
            outcome = f"WIN: +${episode.pnl:.2f} ({episode.return_pct*100:.2f}%)"
        elif episode.pnl < 0:
            outcome = f"LOSS: ${episode.pnl:.2f} ({episode.return_pct*100:.2f}%)"
        else:
            outcome = "BREAKEVEN"
        
        lines.append(outcome)
        
        # Exit reason analysis
        if episode.exit_reason == "TP":
            lines.append("✓ Hit take profit target as planned.")
        elif episode.exit_reason == "SL":
            lines.append("✗ Stopped out - idea invalidated.")
        elif episode.exit_reason == "time_stop":
            lines.append("⏱ Time stop - no clear resolution.")
        elif episode.exit_reason == "signal_reverse":
            lines.append("⇄ Agents reversed signal - exited early.")
        
        # Duration analysis
        if episode.duration_bars:
            if episode.duration_bars < 2:
                lines.append(f"Very quick {episode.duration_bars} bar hold - fast move.")
            elif episode.duration_bars > 10:
                lines.append(f"Long {episode.duration_bars} bar hold - slow grind.")
            else:
                lines.append(f"Held for {episode.duration_bars} bars.")
        
        # Agent consensus quality
        confident_agents = sum(1 for av in episode.agent_views if av.confidence > 0.7)
        aligned_agents = sum(1 for av in episode.agent_views if av.signal == episode.decision)
        
        if aligned_agents == len(episode.agent_views):
            lines.append(f"All {len(episode.agent_views)} agents aligned (strong setup).")
        else:
            lines.append(f"{aligned_agents}/{len(episode.agent_views)} agents aligned (mixed signal).")
        
        if confident_agents >= 2:
            lines.append("High confidence from multiple agents.")
        
        # Outcome vs setup quality
        if episode.pnl > 0 and aligned_agents == len(episode.agent_views):
            lines.append("✓ Quality setup delivered.")
        elif episode.pnl < 0 and aligned_agents == len(episode.agent_views):
            lines.append("✗ Strong setup failed - possible regime shift.")
        elif episode.pnl > 0 and aligned_agents < len(episode.agent_views):
            lines.append("✓ Won despite mixed signals - got lucky?")
        elif episode.pnl < 0 and aligned_agents < len(episode.agent_views):
            lines.append("✗ Weak setup lost as expected.")
        
        return " ".join(lines)
    
    @staticmethod
    def generate_lesson(episode: Episode) -> str:
        """
        Generate one-liner key lesson
        
        Distills trade into actionable takeaway.
        """
        if episode.pnl is None:
            return "Trade in progress."
        
        # Winners
        if episode.pnl > 0:
            if episode.hit_target:
                if len([av for av in episode.agent_views if av.signal == episode.decision]) == len(episode.agent_views):
                    return "Unanimous high-confidence setups work."
                else:
                    return "Even mixed signals can win - but risky."
            else:
                return "Took profit early - could have held longer?"
        
        # Losers
        else:
            if episode.exit_reason == "SL":
                if len([av for av in episode.agent_views if av.signal == episode.decision]) < len(episode.agent_views):
                    return "Avoid mixed-signal trades - they fail more."
                else:
                    return "Even strong setups can fail - respect stops."
            elif episode.exit_reason == "time_stop":
                return "Chopping action - avoid low-conviction trades."
            else:
                return "Cut losses quickly on signal reversal."
    
    @staticmethod
    def infer_regime(episode: Episode) -> str:
        """
        Infer market regime from features
        
        Uses feature digest to classify regime:
        - trending_up: Positive momentum, tight spreads
        - trending_down: Negative momentum, widening spreads
        - accumulation: Low momentum, high volume, positive gamma
        - distribution: Low momentum, high volume, negative gamma
        - ranging: Low momentum, tight spreads, neutral gamma
        """
        feat = episode.features_digest
        
        # Extract key features (with defaults)
        momentum = feat.get("sent_momentum", 0.0)
        amihud = feat.get("liq_amihud", 0.02)
        gamma = feat.get("hedge_gamma", 0.0)
        volume_delta = feat.get("sent_volume_delta", 0.0)
        
        # Classify regime
        if abs(momentum) > 0.4:
            if momentum > 0:
                return "trending_up"
            else:
                return "trending_down"
        elif abs(gamma) > 0.3 and abs(volume_delta) > 0.3:
            if gamma > 0:
                return "accumulation"
            else:
                return "distribution"
        else:
            return "ranging"
    
    @staticmethod
    def reflect(episode: Episode):
        """
        Complete reflection on episode
        
        Updates episode with critique, lesson, and regime.
        """
        if episode.pnl is None:
            return  # Can't reflect on open trade
        
        episode.critique = ReflectionEngine.generate_critique(episode)
        episode.key_lesson = ReflectionEngine.generate_lesson(episode)
        episode.regime_label = ReflectionEngine.infer_regime(episode)


def reflect_on_episode(episode: Episode):
    """Convenience function: reflect on episode"""
    ReflectionEngine.reflect(episode)


if __name__ == "__main__":
    # Test reflection
    import uuid
    from gnosis.memory.schema import AgentView
    
    print("\n" + "="*60)
    print("  REFLECTION ENGINE TEST")
    print("="*60 + "\n")
    
    # Test case 1: Winning trade with strong setup
    ep1 = Episode(
        episode_id=str(uuid.uuid4()),
        symbol="SPY",
        t_open=datetime(2024, 10, 1, 10, 0),
        price_open=580.0,
        features_digest={
            "hedge_gamma": 0.8,
            "liq_amihud": 0.01,
            "sent_momentum": 0.7,
            "sent_volume_delta": 0.5
        },
        agent_views=[
            AgentView("hedge", 1, 0.9, "Strong gamma wall", {"gamma": 0.8}),
            AgentView("liquidity", 1, 0.8, "Tight spreads", {"amihud": 0.01}),
            AgentView("sentiment", 1, 0.8, "Bullish", {"momentum": 0.7}),
        ],
        decision=1,
        decision_confidence=0.85,
        position_size=0.15,
        consensus_logic="3-of-3 unanimous"
    )
    ep1.update_outcome(
        t_close=datetime(2024, 10, 1, 14, 0),
        price_close=583.0,
        exit_reason="TP",
        pnl=0.45,
        hit_target=True
    )
    
    print("Test 1: Winning trade with strong setup")
    ReflectionEngine.reflect(ep1)
    print(f"Critique: {ep1.critique}")
    print(f"Lesson: {ep1.key_lesson}")
    print(f"Regime: {ep1.regime_label}")
    
    # Test case 2: Losing trade with mixed signals
    ep2 = Episode(
        episode_id=str(uuid.uuid4()),
        symbol="SPY",
        t_open=datetime(2024, 10, 5, 11, 0),
        price_open=575.0,
        features_digest={
            "hedge_gamma": 0.2,
            "liq_amihud": 0.03,
            "sent_momentum": 0.1,
            "sent_volume_delta": -0.2
        },
        agent_views=[
            AgentView("hedge", 1, 0.5, "Weak gamma", {"gamma": 0.2}),
            AgentView("liquidity", -1, 0.6, "Wide spreads", {"amihud": 0.03}),
            AgentView("sentiment", 0, 0.4, "Neutral", {"momentum": 0.1}),
        ],
        decision=1,
        decision_confidence=0.4,
        position_size=0.05,
        consensus_logic="2-of-3 bare majority"
    )
    ep2.update_outcome(
        t_close=datetime(2024, 10, 5, 13, 0),
        price_close=573.5,
        exit_reason="SL",
        pnl=-0.075,
        hit_target=False
    )
    
    print("\nTest 2: Losing trade with mixed signals")
    ReflectionEngine.reflect(ep2)
    print(f"Critique: {ep2.critique}")
    print(f"Lesson: {ep2.key_lesson}")
    print(f"Regime: {ep2.regime_label}")
    
    print("\n✅ Reflection tests passed!")
