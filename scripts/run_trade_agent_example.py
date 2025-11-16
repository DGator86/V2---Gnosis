#!/usr/bin/env python3
"""
Example script demonstrating Trade Agent v2.0 usage.

Shows how to:
1. Create a ComposerTradeContext from scratch
2. Generate trade ideas
3. Inspect and rank ideas
"""

from agents.trade_agent import (
    TradeAgentV2,
    ComposerTradeContext,
    Direction,
    ExpectedMove,
    Timeframe,
    VolatilityRegime,
)


def print_divider(title: str):
    """Pretty print section divider."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_trade_idea(idea, rank: int):
    """Pretty print a single trade idea."""
    print(f"\n[{rank}] {idea.strategy_type.value.upper()} - Score: {idea.ranking_score:.3f}")
    print(f"    Asset: {idea.asset}")
    print(f"    Description: {idea.description}")
    print(f"    Confidence: {idea.confidence:.2f}")
    
    if idea.legs:
        print(f"    Legs: {len(idea.legs)}")
        for i, leg in enumerate(idea.legs, 1):
            print(f"      {i}. {leg.side} {leg.option_type} @ {leg.strike:.2f} exp {leg.expiry}")
    
    if idea.max_risk:
        print(f"    Max Risk: ${idea.max_risk:.2f}")
    if idea.max_profit:
        print(f"    Max Profit: ${idea.max_profit:.2f}")
    if idea.recommended_size:
        print(f"    Size: {idea.recommended_size} contracts/shares")
    
    if idea.notes:
        print(f"    Notes: {idea.notes[:150]}...")


def example_bullish_momentum():
    """Example: Bullish momentum scenario."""
    print_divider("Example 1: Bullish Momentum with Vol Expansion")
    
    # Create context
    ctx = ComposerTradeContext(
        asset="SPY",
        direction=Direction.BULLISH,
        confidence=0.75,
        expected_move=ExpectedMove.LARGE,
        volatility_regime=VolatilityRegime.VOL_EXPANSION,
        timeframe=Timeframe.SWING,
        elastic_energy=1.8,
        gamma_exposure=-1.2,
        vanna_exposure=0.6,
        charm_exposure=-0.4,
        liquidity_score=0.95,
    )
    
    # Generate ideas
    agent = TradeAgentV2(default_capital=10_000)
    ideas = agent.generate_trade_ideas(
        ctx=ctx,
        underlying_price=450.0,
        capital=10_000,
    )
    
    print(f"\nGenerated {len(ideas)} trade ideas for {ctx.asset}")
    print(f"Direction: {ctx.direction.value}, Confidence: {ctx.confidence:.2f}")
    print(f"Expected Move: {ctx.expected_move.value}, Vol Regime: {ctx.volatility_regime.value}")
    
    # Print top 5 ideas
    for rank, idea in enumerate(ideas[:5], 1):
        print_trade_idea(idea, rank)


def example_neutral_iron_condor():
    """Example: Neutral range-bound scenario."""
    print_divider("Example 2: Neutral Range-Bound (Iron Condor territory)")
    
    ctx = ComposerTradeContext(
        asset="QQQ",
        direction=Direction.NEUTRAL,
        confidence=0.65,
        expected_move=ExpectedMove.SMALL,
        volatility_regime=VolatilityRegime.LOW,
        timeframe=Timeframe.SWING,
        elastic_energy=0.8,
        gamma_exposure=0.5,  # Positive gamma = pinned
        vanna_exposure=0.1,
        charm_exposure=-0.1,
        liquidity_score=0.90,
    )
    
    agent = TradeAgentV2(default_capital=25_000)
    ideas = agent.generate_trade_ideas(
        ctx=ctx,
        underlying_price=380.0,
        capital=25_000,
    )
    
    print(f"\nGenerated {len(ideas)} trade ideas for {ctx.asset}")
    print(f"Direction: {ctx.direction.value}, Confidence: {ctx.confidence:.2f}")
    print(f"Expected Move: {ctx.expected_move.value}, Vol Regime: {ctx.volatility_regime.value}")
    
    for rank, idea in enumerate(ideas[:5], 1):
        print_trade_idea(idea, rank)


def example_bearish_high_vol():
    """Example: Bearish with high volatility."""
    print_divider("Example 3: Bearish with High Volatility")
    
    ctx = ComposerTradeContext(
        asset="TSLA",
        direction=Direction.BEARISH,
        confidence=0.70,
        expected_move=ExpectedMove.MEDIUM,
        volatility_regime=VolatilityRegime.HIGH,
        timeframe=Timeframe.POSITIONAL,
        elastic_energy=2.5,
        gamma_exposure=-2.0,
        vanna_exposure=-0.8,
        charm_exposure=-0.6,
        liquidity_score=0.75,
    )
    
    agent = TradeAgentV2(default_capital=15_000)
    ideas = agent.generate_trade_ideas(
        ctx=ctx,
        underlying_price=250.0,
        capital=15_000,
    )
    
    print(f"\nGenerated {len(ideas)} trade ideas for {ctx.asset}")
    print(f"Direction: {ctx.direction.value}, Confidence: {ctx.confidence:.2f}")
    print(f"Expected Move: {ctx.expected_move.value}, Vol Regime: {ctx.volatility_regime.value}")
    
    for rank, idea in enumerate(ideas[:5], 1):
        print_trade_idea(idea, rank)


def main():
    """Run all examples."""
    print("\n")
    print("🎯" * 40)
    print("         TRADE AGENT V2.0 - EXAMPLE SCENARIOS")
    print("🎯" * 40)
    
    example_bullish_momentum()
    example_neutral_iron_condor()
    example_bearish_high_vol()
    
    print("\n" + "=" * 80)
    print("  Examples complete! Trade Agent v2.0 is ready for production use.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
